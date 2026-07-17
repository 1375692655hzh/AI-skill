---
name: turkey-info-daily-report-skill
description: Fetches Info Yatirim daily bulletin (Gunluk Bulten) and generates a Chinese prose market analysis report. Use when the user asks for Turkey BIST daily market analysis, Info daily report, gunluk bulten, or pre-market text briefing.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [turkey, borsa, bist, info-yatirim, daily-report, market-analysis]
    related_skills: [turkey-info-technical-report-skill, turkey-morning-report-skill, turkey-close-report-skill]
---

# Turkey Info Daily Report Skill

## Overview

Standalone skill that:

1. Fetches **Info Yatırım Günlük Bülten** (daily market bulletin)
2. Calls a configured LLM to produce a **Chinese prose report** (no tables)

Output is a single text file. No push/delivery is included.

## 开箱即用

给别人用时，**只需这个 skill 目录**，不需要 Turkey-investment 主项目。

| 必需 | 说明 |
|------|------|
| Python 3.9+ | `pip install -r requirements.txt` |
| 网络 | 能访问 `infoyatirim.com` |
| LLM API Key | 默认读 `MINIMAX_API_KEY`；可在 `config.json` 改 provider |
| `config.json` | 仓库已附带，复制目录即可；首次可 `cp config.example.json config.json` |

| 可选 | 说明 |
|------|------|
| Turkey-investment 项目 | 仅当 `use_project_fetcher: true` 时需要；用于读已落盘 Markdown |
| 推送/定时 | 本 skill 只写文件；cron/WhatsApp 由调用方自行配置 |

3 步上手：

```bash
cd turkey-info-daily-report-skill
pip install -r requirements.txt
export MINIMAX_API_KEY="your-key"   # PowerShell: $env:MINIMAX_API_KEY="your-key"
python scripts/generate_info_daily_report.py --config config.json
```

## When to Use

- User asks for「每日市场分析」「Info 日报」「Günlük Bülten 中文报告」
- Pre-market context before BIST opens (15:00 北京 = 10:00 TR)

Do **not** use for technical pivot tables — use `turkey-info-technical-report-skill` instead.

## Recommended Schedule（推荐执行时间）

土耳其时间 TR = UTC+3（全年固定）；北京 = UTC+8；**TR = 北京 − 5 小时**。

| 项目 | 值 |
|------|-----|
| 源站发布时间 (TR) | ~11:00 |
| 源站发布时间 (北京) | ~16:00 |
| **Cron 首发档 (北京)** | **16:20** |
| 重试间隔 | 每 10 分钟 |
| 重试次数 | 6 次（覆盖至 17:10） |
| 兜底 | **20:00** 再 1 次 |
| 周末/土耳其节假日 | 跳过，不重试 |

Cron 时间点（北京时间，交易日）：

```
16:20, 16:30, 16:40, 16:50, 17:00, 17:10  → 首发循环
20:00                                       → 兜底
```

Borsa İstanbul 交易时段：10:00–18:00 TR = **15:00–23:00 北京**。本报告在开盘前发布，适合 16:20 后抓取。

## Data Source

| Source | URL | Publish (TR) | Publish (Beijing) |
|--------|-----|--------------|-------------------|
| Info Yatırım Günlük Bülten | https://infoyatirim.com/arastirma/gunluk-bulten | ~11:00 | ~16:00 |

Fetch modes:

- **Direct** (default): scrape archive page + CDN HTML
- **Project** (optional): `sources.info_daily.use_project_fetcher: true` + `project_path` → calls Turkey-investment `fetch.py info-daily`

## Outputs

- `{output_dir}/{date}_info_daily_report_zh.txt` — 600–1200 字纯文字报告

Default output directory: `output/`

## Run Flow

1. Resolve target date (TR trading day; weekend/holiday → skip)
2. Fetch Günlük Bülten (with date verification)
3. Build LLM prompt from template + sanitized source
4. Call LLM + validate format (prose only, no tables)
5. Write output file

## Configuration

| Key | Purpose |
|-----|---------|
| `output_dir` | Finished report location |
| `cache_dir` | Raw bulletin + prompt cache |
| `sources.info_daily.use_project_fetcher` | Use Turkey-investment `fetch.py` |
| `sources.info_daily.project_path` | Path to Turkey-investment project |
| `llm` | Provider, model, API key env var |
| `holidays` | Optional extras only; fixed TR holidays auto-generated (Jun+ includes next year) |

## Format Rules

- Only `【】` section headers
- **No tables**, bullets, emojis, or Markdown separators
- Sections: 核心观点 → 隔夜要闻 → 昨日收盘回顾 → 今日展望 → 关键数据 → 操作建议 → 风险提示
- No source attribution in output

## Example Invocation

```bash
pip install -r requirements.txt
export MINIMAX_API_KEY="your-key"
python scripts/generate_info_daily_report.py --config config.json
python scripts/generate_info_daily_report.py --config config.json --force-date 2026-07-14
python scripts/generate_info_daily_report.py --config config.json --no-llm
```

See `SETUP.md` for full deployment instructions.

## Common Pitfalls

1. **Running before publish time (~16:00 Beijing).** Bulletin may not exist yet; script reports `not_found` with fallback URL.
2. **Weekend/holiday.** Skill skips generation.
3. **Stale cache.** Date mismatch triggers cache discard and re-fetch.

## License

MIT
