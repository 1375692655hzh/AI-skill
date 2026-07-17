## 数据源详情

### 1. BloombergHT 详细收盘（Piyasalarda günün özeti）

| 项目 | 内容 |
|------|------|
| 发布时间 | TR ~18:30 / 北京 ~23:30 |
| 角色 | **核心收盘数据** |
| 股市栏目 | https://www.bloomberght.com/borsa |
| RSS | https://www.bloomberght.com/rss |
| 文章探测格式 | `https://www.bloomberght.com/x-{文章ID}` |
| 示例 URL | https://www.bloomberght.com/piyasalarda-gunun-ozeti-10-temmuz-2026-bist-100-de-degisimler-ve-doviz-fiyatlari-pkh-3782616 |
| 标题新格式 | `Piyasalarda günün özeti: {date} ...` |
| 标题旧格式 | `Piyasa özeti: {date} ...` |

抓取策略：
1. 先读取 RSS feed，匹配标题中的 `Piyasalarda günün özeti` 或 `Piyasa özeti`
2. 用标题中的日期确定是否匹配 target_date
3. 如 RSS 失败，fallback 到 borsa 主页抓取
4. 最后 fallback 到文章 ID 探测

BIST 100 收盘价、涨跌幅、成交量、USD/TRY、EUR/TRY、黄金、原油等**所有核心收盘数据**均来自此来源。

### 2. Paraborsa 券商评论（Borsa Yorumu）

| 项目 | 内容 |
|------|------|
| 发布时间 | TR ~16:30 / 北京 ~21:30 |
| 角色 | 辅助观点 / 技术分析 |
| 首页 | https://www.paraborsa.net/ |
| 详情页格式 | `https://www.paraborsa.net/i/borsa-yorumu-{券商slug}-{日}-{月}-{年}/` |
| 示例 | https://www.paraborsa.net/i/borsa-yorumu-destek-yatirim-8-07-2026/ |
| REST API | `https://www.paraborsa.net/wp-json/wp/v2/posts?slug=borsa-yorumu-{slug}-{date}` |

券商优先级：
1. Destek Yatırım
2. Bizim Yatırım
3. Bulls
4. İnfo Yatırım
5. Integral Yatırım
6. 其他

同日多家券商只取 1 份，按优先级选择。

抓取策略：
1. 先抓首页，列出当日所有券商评论链接
2. 按优先级排序，选择最优先的 1 份
3. 如首页没有，用 WP REST API 对优先级券商逐个探测

此来源仅用于补充观点、技术位、个股推荐，**不用于覆盖 BloombergHT 的收盘数据**。

### 3. Info Yatırım 每日公告（Günlük Bülten）

| 项目 | 内容 |
|------|------|
| 发布时间 | TR ~11:00 / 北京 ~16:00 |
| 角色 | 辅助研报 |
| 着陆页 | https://infoyatirim.com/arastirma/gunluk-bulten |
| 按日期归档页 | `https://infoyatirim.com/arastirma/gunluk-bulten/gunluk-bulten-{DDMMYYYY}/{ID}` |
| 正文 | `https://cdn.infoyatirim.com/Content/Bulletin/{uuid}.html` |
| 研究总入口 | https://infoyatirim.com/arastirma |

抓取策略：
1. 先按目标日期构造归档页 URL，提取 `/Content/Bulletin/{uuid}.html` 链接
2. 用 UUID 拼接正文 URL，抓取 HTML 文本
3. 归档页失败时，fallback 到着陆页最新公告

### 4. Info Yatırım 技术分析（Teknik Bülten）

| 项目 | 内容 |
|------|------|
| 发布时间 | TR ~12:00 / 北京 ~17:00 |
| 角色 | 辅助技术位 |
| 着陆页 | https://infoyatirim.com/arastirma/teknik-bulten |
| 按日期归档页 | `https://infoyatirim.com/arastirma/teknik-bulten/teknik-bulten-{DDMMYYYY}/{ID}` |
| 正文 | `https://cdn.infoyatirim.com/Content/Bulletin/{uuid}.html` |
| 研究总入口 | https://infoyatirim.com/arastirma |

抓取策略：
1. 先按目标日期构造归档页 URL，提取 `/Content/Bulletin/{uuid}.html` 链接
2. 用 UUID 拼接正文 URL，抓取 HTML 文本
3. 归档页失败时，fallback 到着陆页最新公告

---

## 日期校验机制

`generate_close_report.py` 在抓取每个数据源后会调用 `check_source_date.is_content_for_date()` 进行校验：

| 源 | 校验逻辑 |
|----|----------|
| BloombergHT | 严格匹配目标日期 |
| Paraborsa | 从标题 `(DD.MM.YYYY)` 严格匹配目标日期 |
| Info Yatırım | 从归档页标题提取日期；允许 ±1 天容忍（盘前简报特性） |

若缓存内容日期不匹配，该来源缓存会被删除并重新抓取。