# 港股新股推送文案规范（已固化 2026-08-07）

本文件为提醒模板与每日摘要的**唯一风格基准**，`templates/reminder_*.txt` 的字段填充依此编写。改风格先改这里，再同步模板。

## 通用文风——「结构化字段 + 做减法」

- **机构投研冷峻客观，事实先行**。不加口语/戏剧化点评，禁「神股/稳赚/必涨/打新必中/暴利/抢权」等夸大词。
- **数字一律来自 DB**（`state.db.companies`），简报无则**静默省略**或写 `—`，**禁编造、禁占位、禁从记忆补**。
- 缺字段时直接省略该行，不写「暂无」「待更新」等说明句（写「暂无」本身就是废话）。
- 日期统一 `YYYY-MM-DD`，时间统一 24 小时制 `HH:MM`，港元金额不带「HK$」前缀（统一「港元」）。
- 公司名带股票代码括注：`蜜雪集团（02297.HK）`。
- 招股价写区间：`7.50–9.50 港元`；单一定价写 `8.50 港元`。
- 总市值/流通市值统一「亿港元」，保留 1 位小数（如 `102.5 亿港元`）。
- 暗盘时间固定写 `16:15–18:30`（半日市 `14:15–16:30`）。

## 提醒文案结构（7 类事件，每类一个模板）

每条推送含：标题（事件类型 + 日期） + 公司卡（公司/代码/业务/招股价/手数/市值） + 时间表（开始招股/融资截止/现金截止/解冻/暗盘/上市） + 招股书链接。缺哪行省哪行。

| 事件类型 | 标题前缀 | 模板文件 |
|---|---|---|
| `offer_open` | 港股新股·招股开始 | `templates/reminder_offer_open.txt` |
| `cash_close` | 港股新股·现金截止 | `templates/reminder_cash_close.txt` |
| `margin_close` | 港股新股·融资截止 | `templates/reminder_margin_close.txt` |
| `refund` | 港股新股·资金解冻 | `templates/reminder_refund.txt` |
| `grey_open` | 港股新股·暗盘开始 | `templates/reminder_grey.txt`（slot=open） |
| `grey_close` | 港股新股·暗盘结束 | `templates/reminder_grey.txt`（slot=close） |
| `listing` | 港股新股·今日上市 | `templates/reminder_listing.txt` |

## 每日摘要结构（`daily_digest.md`）

```markdown
# 港股新股每日变动 — {YYYY-MM-DD}（周x）

## 新递表
- {公司名}（递表日期 / 行业 / 保荐人）

## 新聆讯（PHIP 出现）
- {公司名}（PHIP 发布日 / 预计招股窗口）

## 新招股
- {公司名}（{代码}） 招股价 {min}–{max} 港元 / 每手 {lot} 股 / 招股期 {open}–{close}

## 招股中（截至 {date}）
| 公司 | 代码 | 招股价 | 每手 | 截止 | 上市日 |
|...|

## 即将上市（7 天内）
- {公司名}（{代码}） 上市日 {date} / 暗盘 {grey_date} 16:15–18:30

## 数据源状态
- HKEX appindex: OK / 降级（原因）
- Tiger JSON: OK / 降级
- AAStocks: OK / 降级
```

## 推送格式（webhook）

- **Bark / Server酱**：纯文本，每条提醒一条推送
- **企业微信**：纯文本（markdown 支持有限，用 `**粗体**` + 普通列表，禁表格）
- 多事件同 slot → 合并为一条推送（避免刷屏），每事件一段，`---` 分隔

## 数据管线关键

- HKEX appindex diff 是 新递表 / 聆讯(PHIP) 的金标准（`scripts/collectors/hkex_appindex.py`）
- Tiger JSON `hktrade.skytigris.com` 是结构化主源（招股价/手数/截止/暗盘时间/上市日）（`scripts/collectors/tiger_ipo.py`）
- AAStocks 做 正在招股/擬上市/暗盘价 交叉校验（`scripts/collectors/aastocks_ipo.py`）
- 招股书 PDF 預期時間表 regex 提取融资截止/退款（`scripts/collectors/hkex_prospectus_pdf.py`）
- 三源归一在 `lib/normalize.py`，事件日期计算在 `lib/compute_events.py`
- 任一源失败 → 静默降级（不阻断主流程），在 daily_digest.md 标注

## 定时（北京时间 = HKT，工作日）

- 07:30 主刷新
- 08:30 现金截止提醒 / 09:00 招股开始+上市 / 13:30 融资截止 / 16:00 暗盘开始 / 17:00 资金解冻 / 18:15 暗盘结束
- 周日 03:00 清理（上市满 30 天归档，90 天删除，原始快照 14 天删）
