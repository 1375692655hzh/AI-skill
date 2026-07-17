# 部署指南 — Turkey Paraborsa All-Broker Report Skill

全量抓取 Paraborsa 当日所有券商评论，生成「综合总结 + 拼接内容」报告。

---

## 开箱即用清单

| # | 项目 |
|---|------|
| 1 | 复制 `turkey-paraborsa-all-report-skill` 目录 |
| 2 | `pip install -r requirements.txt` |
| 3 | 设置 `MINIMAX_API_KEY`（或其他 LLM） |
| 4 | 运行 `generate_paraborsa_all_report.py` |

不需要 Turkey-investment 项目。

---

## 安装

```bash
cd turkey-paraborsa-all-report-skill
pip install -r requirements.txt
cp config.example.json config.json   # 首次可选
$env:MINIMAX_API_KEY = "你的key"
```

---

## 运行

```bash
# 生成今日全量报告
python scripts/generate_paraborsa_all_report.py --config config.json

# 指定日期（历史日期靠 REST 反查，不依赖首页）
python scripts/generate_paraborsa_all_report.py --config config.json --force-date 2026-07-14

# 只抓取+拼接，不调 LLM（测试用）
python scripts/generate_paraborsa_all_report.py --config config.json --force-date 2026-07-14 --no-llm

# 忽略缓存重新抓取
python scripts/generate_paraborsa_all_report.py --config config.json --force-refresh
```

### 输出文件

| 路径 | 内容 |
|------|------|
| `output/{date}_paraborsa_all_report_zh.txt` | 完整报告 |
| `output/{date}_paraborsa_concat.txt` | 仅拼接部分 |
| `.cache/turkey-paraborsa-all-report/paraborsa_all_{date}.json` | 抓取缓存 |

---

## 推荐 Cron（北京时间）

Paraborsa 评论在收盘后陆续发布，建议比单篇优选 skill 稍晚：

```cron
0  22 * * 1-5  cd /path/to/turkey-paraborsa-all-report-skill && python scripts/generate_paraborsa_all_report.py --config config.json
10 22 * * 1-5  ...
20 22 * * 1-5  ...
30 22 * * 1-5  ...
0  23 * * 1-5  ...
```

---

## 配置说明

| 键 | 说明 |
|----|------|
| `fetch.delay_seconds` | 每篇间隔，防 429（默认 1.2s） |
| `fetch.article_types` | 纳入的文章类型前缀 |
| `fetch.include_period_ranges` | 周期文章（14.07–21.07）算起始日 |
| `summary.excerpt_chars_per_article` | 送入 LLM 的每篇摘录长度 |
| `llm.max_tokens` | 建议 ≥ 12000 |

---

## 常见问题

**Q: 为什么比 `fetch.py paraborsa` 慢？**
→ 全量要抓 20–30 篇，每篇 REST + 间隔，约 1–3 分钟。

**Q: 7/14 有多少篇？**
→ REST 全站搜索实测 **27 篇**（23 Borsa Yorumu + 1 盘中 + 3 VİOP）。

**Q: 拼接内容是中文还是土耳其语？**
→ 默认开启 `translate_concat.enabled`，拼接部分译为**中文**；综合总结始终为中文。设 `false` 或 `--no-llm` 可保留土耳其语原文。

**Q: REST 429 怎么办？**
→ 增大 `fetch.delay_seconds` 到 2.0，或用 `--force-refresh` 重试。
