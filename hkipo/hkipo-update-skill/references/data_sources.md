# 数据源（港股新股）

数据源优先级和判定逻辑对齐 HKIPO 项目（`D:\AI项目\HKIPO`），把 HKEX 官方源作为金标准。

## 判定逻辑（与 HKIPO 项目一致）

| 事件 | 判定来源 | 备注 |
|------|---------|------|
| 新递表 | HKEX `appactive_app_sehk_c.json` 出现的 applicant | 通过 `ls[]` 抽 `ap_date`（最早 `申請版本` 日期） |
| 新聆讯 | HKEX `appactive_appphip_sehk_c.json` 或 `hasPhip=true` | HKEX 不公布命名聆讯名单；PHIP 出现即代理「聆讯通过」。通过 `ls[]` 抽 `phip_date`（最晚 `聆訊` 日期） |
| **新招股** | **HKEX 新上市信息页（主板+GEM）+ 招股文件页（predefineddoc）并集** | **主判定源**。覆盖「已发招股书但申购未开始」公司，比 Tiger `OPEN` 更早。移植自 HKIPO 项目 `ipo_sync.py:fetch_merged_ipo_listings` |
| 新上市 | HKEX `applisted_sehk_c.json` + lifecycle 升级（listing_date <= today） | HKEX 是金标准 |
| 招股详细字段（招股价/每手/市值/截止时间） | Tiger JSON + 招股书 PDF | Tiger 作为字段补充源（不再作为 in_offer 状态判定） |

## 数据源 URL 速查

| 源 | URL | 用途 |
|----|-----|------|
| HKEX appindex (JSON) | `https://www1.hkexnews.hk/ncms/json/eds/appactive_app_sehk_c.json` 等 4 个 | 新递表 / PHIP / 已上市 / 退回（金标准基线） |
| **HKEX 新上市信息（HTML）** | `https://www2.hkexnews.hk/New-Listings/New-Listing-Information/Main-Board?sc_lang=zh-HK` + `/GEM` | **招股主判定**（5 列：代码/名称/公告/招股书/分配结果） |
| **HKEX 招股文件（HTML）** | `https://www1.hkexnews.hk/search/predefineddoc.xhtml?lang=zh&predefineddocuments=6` | 最近 7 天招股文件（与新上市页 union） |
| HKEX titleSearch | `POST https://www1.hkexnews.hk/search/titleSearchServlet.do` | 招股书 PDF 链接（fallback） |
| HKEX 活跃股票映射 | `https://www1.hkexnews.hk/ncms/script/eds/activestock_sehk_c.json` | 股票代码 → 数字 stockId |
| Tiger IPO JSON | `https://hktrade.skytigris.com/ipos/general/hk?status=OPEN|LISTED&lang=zh_CN` | 字段补充：招股价/手数/截止/暗盘/上市 |
| AAStocks 新股中心 | `https://hk.aastocks.com/sc/stocks/market/ipo/mainpage.aspx` | 交叉校验（AJAX 空壳，常 0 行） |

## 字段主备源

| 字段 | 主源 | 备份 | 备注 |
|------|------|------|------|
| 新递表 / 聆讯(PHIP) | HKEX appindex JSON | — | HKEX 不公布命名聆讯名单；PHIP 出现即代理「聆讯通过」 |
| **in_offer（招股状态）** | **HKEX 新上市信息页 + 招股文件页** | Tiger `status=OPEN` | HKEX 主判定更早；Tiger 只在申购期内有效 |
| 招股价 / 板数 / 公开发售股数 | Tiger skytigris JSON | AAStocks HTML | Tiger 结构化最全 |
| 招股开始 / 现金截止 | **招股书 PDF 預期時間表 regex**（20+ 模式 + OCR 归一化） | Tiger JSON | PDF 是金标准；移植自 HKIPO `ipo_lifecycle.py` |
| 融资截止(孖展) | 派生：cash_close − 1 **自然日** | — | 港股惯例，HKIPO 项目 `ipo_calendar.py` 同口径 |
| 资金解冻 / 退款 | 招股书 PDF 預期時間表 regex | 派生：listing − 2 港股交易日 | HKIPO 项目同口径 |
| 暗盘日期 | 派生：listing_date − 1 港股交易日 | — | 时间固定 16:15–18:30 HKT |
| 上市日 | HKEX appindex listed + 新上市信息页 | Tiger listDate | HKEX 是金标准 |

## 失败降级矩阵

| 失败的源 | 影响 | 降级行为 |
|---|---|---|
| HKEX appindex JSON | 新递表/新聆讯可能漏 | daily_digest.md 标注 |
| HKEX 新上市信息页 | in_offer 漏判 | Tiger `status=OPEN` 兜底（但只在申购期内有效，会延迟 1-3 天） |
| Tiger JSON | 招股价/手数/截止字段缺 | AAStocks HTML 补；HKEX PDF 預期時間表补日期 |
| AAStocks | 失去交叉校验 | HKEX+Tiger 仍能完成；daily_digest.md 标注 |
| HKEX PDF | 缺融资截止/退款日期 | 这些字段从 Tiger/AAStocks 取；融资截止按 cash_close − 1 自然日 推 |

所有源都失败 → `run_update.py` 退出 1；至少一个源成功即继续。

## 频率纪律

- HKEX / Tiger / AAStocks 都是免费免登录，且**未明文限速**，但社区共识是「请勿高频运行」
- 本 skill 默认 **每日 07:30 刷一次**（外加 PDF 解析 max 5 份）；6 个提醒 slot 只查本地 SQLite，不调网络
- 如需提高频率（例如 IPO 当天中午也想刷新暗盘价），可手动跑 `python scripts/run_update.py`，不会重复插入事件（events 表 UPSERT 幂等）

## 招股书 PDF 預期時間表 关键字段（regex 提取）

正则集移植自 HKIPO 项目 `ipo_lifecycle.py`，覆盖以下变体：

| 字段 | 关键词模式 | 数量 |
|------|-----------|------|
| offer_open_date | `公开发售开始` / `开始公开发售` | 2 条 |
| cash_close_date | `香港公開發售截止辦理申請登記` / `截止辦理申請登記` / `完成電子申請的截止時間` / `遞交香港公開發售申請截止日期` | 4 条 |
| allotment_date | `公[佥布]配[發发]結果` | 1 条 |
| refund_date | `寄發退款` / `退回款項` / `退款支票` / `資金解凍` | 1 条 |
| **listing_date** | `開始買賣..` 时间表行 / `预期将于…开始…联交所买卖` / `將於…在聯交所開始買賣` / `「上市日期」指…開始買賣的日期，預期為…` / `開始買賣日期…` 分配结果公告 等 | **13 条** |

解析前对 PDF 文本做 OCR 归一化（`_normalize_prospectus_text`）：
- 「開 始 買 賣」→ 「開始買賣」（CJK 间空格归零）
- 「2026 年 6 月 30 日」→ 「2026年6月30日」（CN 日期空格归零）
- 「H 股」→ 「H股」

PDF 解析使用 pdfplumber，扫描前 25 页（招股书時間表通常在前 15 页，多扫一些防止跨页模式失败）。所有 loose match 加 ±1 年 sanity check，防止误抓合同/预测年份。

## HKEX ID 漂移 / 同名去重

同一 applicant 可能多次递表（HKEX 每次分配新 id）。`normalize.score_name_similarity` 提供 fuzzy 匹配作为辅助：
- 完全相等 → 1.0
- 子串包含 → 0.95
- brand_key 相等（剥除「股份/有限/公司/集团/科技」等后缀） → 0.88-0.9
- 否则 difflib SequenceMatcher 比例

阈值 ≥0.82 视为同一家。当前 merge 阶段不强制使用，留给后续跨日 DB 比对场景（同 stock_code 多次递表归并）。
