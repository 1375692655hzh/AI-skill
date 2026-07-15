---
name: turkey-close-report-skill
description: Use when generating a Turkish stock market close-of-day report in Chinese, based on the same-day BloombergHT closing review, Paraborsa broker commentary, and Info Yatırım bulletins.
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [turkey, borsa, bist, close-report, market-briefing, investment]
    related_skills: [turkey-morning-report-skill]
---

# Turkey Close Report Skill

## Overview

A standalone skill for generating a Chinese-language Turkish stock market close-of-day report.

Unlike the morning report, the close report:
- Focuses on summarizing the **same trading day's** market action
- Includes **broker commentary** and **technical analysis**
- Does **not** include international news

### Data Source Hierarchy

| Source | Role | Content |
|--------|------|---------|
| BloombergHT Piyasalarda günün özeti | **Primary** | BIST 100 close, sectors, stocks, FX, commodities, volume |
| Paraborsa broker commentary | Supplementary | Broker views, technical levels, stock picks |
| Info Yatırım daily bulletin | Supplementary | Pre-market summary and outlook |
| Info Yatırım technical bulletin | Supplementary | Support/resistance, technical signals |

**Important:** Closing figures (BIST 100 close, change %, volume, USD/TRY, EUR/TRY, gold, oil) must come from BloombergHT. The supplementary sources are only used for technical levels, broker opinions, and market sentiment.

### Source Date Verification

Every source has a date guard. After fetching, the skill checks whether the fetched content actually matches the target date. If the cached content is stale or misaligned (e.g., a Monday report was accidentally cached with Friday's data), the cache is discarded and the source is re-fetched. Info Yatırım bulletins are published pre-market, so they are allowed a ±1 day tolerance relative to the target date.

## When to Use

- **推荐运行时间：北京时间 23:30+**（土耳其时间 18:30+，收盘后）
  - BloombergHT 详细收盘已发布
  - Paraborsa 券商评论已发布
  - Info Yatırım 公告已发布
- 适用于收盘后复盘、次日开盘前参考

## Inputs the Caller Must Provide

1. A configured LLM API that can read Turkish and write Chinese
2. Environment variables for the chosen LLM provider (see `SETUP.md`)
3. Python 3.9+ with `requirements.txt` dependencies

## Outputs

- **完整版**：`{output_dir}/{date}_close_report_zh.txt`（800–1500 字）
- **简报版**：`{output_dir}/{date}_close_report_brief_zh.txt`（400–650 字，【字段】结构化，个股每只一行）
- Default output directory: `output/`

## Run Flow

1. Resolve target date in Turkey time (today's business day)
2. Fetch BloombergHT close-of-day review + breaking/featured news
3. Fetch Paraborsa broker commentary (priority: Destek > Bizim > Bulls > İnfo > Integral)
4. Fetch Info Yatırım daily bulletin + technical bulletin from **date-specific archive pages** (not only the latest landing page)
5. Run **source date verification**; discard stale cache and re-fetch if mismatched
6. Build prompt from the template and collected data
7. Call the configured LLM
8. Validate output format (full + brief)
9. Write files and return paths

Brief format (one field per line):

```
【土耳其股市收评简报 — {date}（周x）】
指数：...
汇率：...
驱动：...
个股：...
板块：...
信号：...
操作：...
风险：...
```

## Data Sources

| Source | Timing | Role | Content |
|--------|--------|------|---------|
| BloombergHT 详细收盘 | TR ~18:30 | **Primary** | BIST 100, sectors, stocks, forex, commodities |
| Paraborsa 券商评论 | TR ~16:30 | Supplementary | Broker commentary, technical analysis |
| Info Yatırım 每日公告 | TR ~11:00 | Supplementary | Daily bulletin, stock recommendations |
| Info Yatırım 技术分析 | TR ~12:00 | Supplementary | Technical analysis, support/resistance |

Closing numbers and index changes must come from BloombergHT. The other sources are used only for technical levels, broker opinions, and sentiment.

## Configuration

See `config.json`. Key knobs:

| Key | Purpose |
|-----|---------|
| `output_dir` | Where the finished report is saved |
| `cache_dir` | Where raw fetched data is cached |
| `llm` | Provider, model, API key env var, base URL |
| `holidays` | Turkish market holidays to skip |
| `brief.enabled` | Generate structured brief version (default `true`) |
| `brief.min_chars` / `brief.max_chars` | Brief length bounds (default 400–650) |

## Format Rules

- Only `【】` as section headers
- No tables, bullets, emojis, bold/italic markers
- Sections:
  1. `【土耳其股市收评 — {date}（{weekday}）】` + 核心结论
  2. `【大盘概况】`
  3. `【关键个股异动】`
  4. `【行业板块表现】`
  5. `【汇市与大宗商品】`
  6. `【核心信号与逻辑】`
  7. `【后市策略参考】`
  8. `风险提示：`

## Example Invocation

```bash
pip install -r requirements.txt
export MINIMAX_API_KEY="your-key"
python scripts/generate_close_report.py --config config.json
```

See `SETUP.md` for deployment across Cursor, Codex, Hermes, OpenClaw, and WorkBuddy.

## License

MIT
