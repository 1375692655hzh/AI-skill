---
name: turkey-paraborsa-all-report-skill
description: Fetches ALL Paraborsa broker commentaries for a trading day via WordPress REST API and generates a Chinese synthesis report with ticker/source/view summary plus concatenated full texts. Use when the user asks for full Paraborsa broker roundup, all broker views, or comprehensive券商评论汇总.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [turkey, borsa, bist, paraborsa, broker-commentary, all-brokers, synthesis]
    related_skills: [turkey-close-report-skill, turkey-info-daily-report-skill]
---

# Turkey Paraborsa All-Broker Report Skill

## Overview

Unlike single-pick `paraborsa` fetchers, this skill:

1. **Discovers all** Paraborsa posts for the target date (REST search + slug probe)
2. **Fetches every body** (rate-limited REST, 429 retry)
3. Outputs a two-part Chinese report:
   - **【综合总结】**：全量标的 + 来源券商 + 看法（LLM）
   - **【拼接内容】**：各券商原文逐篇拼接（机械拼接，不改写）

## 开箱即用

| 必需 | 说明 |
|------|------|
| Python 3.9+ | `pip install -r requirements.txt` |
| 网络 | `paraborsa.net` WordPress REST API |
| LLM API Key | 默认 `MINIMAX_API_KEY`（仅用于综合总结部分） |
| 复制 skill 目录 | 含 `config.json` |

**不需要** Turkey-investment 主项目。

```bash
cd turkey-paraborsa-all-report-skill
pip install -r requirements.txt
export MINIMAX_API_KEY="your-key"
python scripts/generate_paraborsa_all_report.py --config config.json
```

## Recommended Schedule（推荐执行时间）

| 项目 | 时间 |
|------|------|
| Paraborsa 源站发布 | TR ~16:30 / 北京 ~21:30 |
| **Cron 首发** | **北京时间 22:00**（确保当日评论基本齐） |
| 重试 | 22:10、22:20、22:30 |
| 兜底 | **23:00** |
| 周末/土节假日 | 跳过 |

```
22:00, 22:10, 22:20, 22:30  → 首发循环
23:00                         → 兜底
```

## Outputs

| 文件 | 说明 |
|------|------|
| `output/{date}_paraborsa_all_report_zh.txt` | 完整报告（总结 + 拼接） |
| `output/{date}_paraborsa_concat.txt` | 仅拼接内容（便于单独阅读） |
| `.cache/.../paraborsa_all_{date}.json` | 全量抓取缓存 |

## Report Structure

```
【综合总结 — YYYY-MM-DD（周x）】
宏观与市场共识
个股覆盖汇总（表格：标的 | 提及券商 | 看法摘要）
券商观点速览
分歧点

【拼接内容 — YYYY-MM-DD（周x）】
--- 第1篇 | Destek Yatırım | Borsa Yorumu ---
（土耳其语原文全文）
...
```

## Date Matching Rules

计入目标日 `YYYY-MM-DD` 的文章：

- 标题/slug 含 `DD.MM.YYYY` 或 `D-MM-YYYY`
- 周期文章以目标日为起点（如 `14.07.2026 - 21.07.2026` 算 7/14）

## Article Types (configurable)

- `borsa-yorumu`（收盘评论，主力）
- `gun-ici-borsa-yorumu`（盘中）
- `viop-yorumu`（衍生品）
- `haftalik-borsa-yorumu`（周报，若标题匹配日期）

## Example

```bash
python scripts/generate_paraborsa_all_report.py --config config.json --force-date 2026-07-14
python scripts/generate_paraborsa_all_report.py --config config.json --no-llm
python scripts/generate_paraborsa_all_report.py --config config.json --force-refresh
```

## vs Single-Pick Skill

| | `fetch.py paraborsa` | 本 skill |
|---|---|---|
| 篇数 | 1 篇（优先级优选） | 全量（实测可达 20–30 篇/日） |
| 发现方式 | 首页 | REST 全站搜索 |
| 历史日期 | 首页滚走后难找 | REST 可反查 |
| 输出 | 单篇 Markdown | 总结 + 拼接综合报告 |

## License

MIT
