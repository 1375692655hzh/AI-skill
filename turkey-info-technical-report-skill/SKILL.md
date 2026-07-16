---
name: turkey-info-technical-report-skill
description: Fetches Info Yatirim technical bulletin (Teknik Bulten) and generates a Chinese technical analysis report with markdown tables for BIST100 pivots, RSI/CCI signals, and stock levels. Use when the user asks for Turkey BIST technical analysis, Info technical report, teknik bulten, pivot/support/resistance tables.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [turkey, borsa, bist, info-yatirim, technical-analysis, pivot, rsi, cci]
    related_skills: [turkey-info-daily-report-skill, turkey-close-report-skill]
---

# Turkey Info Technical Report Skill

## Overview

Standalone skill that:

1. Fetches **Info Yatırım Teknik Bülten** (technical bulletin)
2. Calls a configured LLM to produce a **Chinese table-focused report**

Tables are the primary output format (pivot levels, RSI/CCI overbought/oversold, volume leaders, per-stock technical levels).

## 开箱即用

给别人用时，**只需这个 skill 目录**，默认 direct 抓取即可独立运行。

| 必需 | 说明 |
|------|------|
| Python 3.9+ | `pip install -r requirements.txt` |
| 网络 | 能访问 `infoyatirim.com` |
| LLM API Key | 默认读 `MINIMAX_API_KEY`；技术报告建议 `max_tokens ≥ 12000` |
| `config.json` | 仓库已附带，复制目录即可 |

| 可选（推荐） | 说明 |
|------|------|
| Turkey-investment 项目 | `use_project_fetcher: true` 时读取已落盘 Markdown，表格更完整 |
| 推送/定时 | 本 skill 只写文件；cron 由调用方配置 |

3 步上手：

```bash
cd turkey-info-technical-report-skill
pip install -r requirements.txt
export MINIMAX_API_KEY="your-key"
python scripts/generate_info_technical_report.py --config config.json
```

## When to Use

- User asks for「技术分析」「技术位」「Pivot/支撑阻力」「RSI/CCI 超买超卖」
- Full-market technical snapshot (not single-ticker KB lookup)

Do **not** use for prose daily market narrative — use `turkey-info-daily-report-skill` instead.

## Recommended Schedule（推荐执行时间）

土耳其时间 TR = UTC+3（全年固定）；北京 = UTC+8；**TR = 北京 − 5 小时**。

| 项目 | 值 |
|------|-----|
| 源站发布时间 (TR) | ~12:00 |
| 源站发布时间 (北京) | ~17:00 |
| **Cron 首发档 (北京)** | **17:20** |
| 重试间隔 | 每 10 分钟 |
| 重试次数 | 6 次（覆盖至 18:10） |
| 兜底 | **20:00** 再 1 次 |
| 周末/土耳其节假日 | 跳过，不重试 |

Cron 时间点（北京时间，交易日）：

```
17:20, 17:30, 17:40, 17:50, 18:00, 18:10  → 首发循环
20:00                                       → 兜底
```

Borsa İstanbul 交易时段：10:00–18:00 TR = **15:00–23:00 北京**。技术公告在盘中发布，适合 17:20 后抓取。

## Data Source

| Source | URL | Publish (TR) | Publish (Beijing) |
|--------|-----|--------------|-------------------|
| Info Yatırım Teknik Bülten | https://infoyatirim.com/arastirma/teknik-bulten | ~12:00 | ~17:00 |

Fetch modes:

- **Direct** (default): scrape archive page + CDN HTML
- **Project** (optional): `sources.info_technical.use_project_fetcher: true` + `project_path` → calls Turkey-investment `fetch.py info-technical` (returns Markdown with tables)

## Outputs

- `{output_dir}/{date}_info_technical_report_zh.txt` — 表格为主的中文技术报告

Default output directory: `output/`

## Run Flow

1. Resolve target date (TR trading day)
2. Fetch Teknik Bülten (with date verification)
3. Build LLM prompt from template + sanitized source
4. Call LLM + validate format (requires ≥4 markdown tables)
5. Write output file

## Configuration

| Key | Purpose |
|-----|---------|
| `output_dir` | Finished report location |
| `cache_dir` | Raw bulletin + prompt cache |
| `sources.info_technical.use_project_fetcher` | Use Turkey-investment `fetch.py` (recommended for richer tables) |
| `sources.info_technical.project_path` | Path to Turkey-investment project |
| `llm` | Provider, model, API key env var (`max_tokens` ≥ 12000 recommended) |
| `holidays` | Borsa İstanbul closed dates |

## Format Rules

- `【】` section headers + **Markdown tables** for all numeric data
- Required tables: BIST100 levels, CCI/RSI signals, volume leaders, stock pivot grid
- Short prose sections: 核心观点, 技术信号解读, 操作建议, 风险提示
- No source attribution in output

## Example Invocation

```bash
pip install -r requirements.txt
export MINIMAX_API_KEY="your-key"
python scripts/generate_info_technical_report.py --config config.json
python scripts/generate_info_technical_report.py --config config.json --force-date 2026-07-09
python scripts/generate_info_technical_report.py --config config.json --no-llm
```

See `SETUP.md` for full deployment instructions.

## Common Pitfalls

1. **Running before publish time (~17:00 Beijing).** Bulletin may not exist yet.
2. **LLM truncating tables.** Set `max_tokens` to 12000+.
3. **Single-ticker lookup.** For one stock's technicals, use Turkey-investment `bist-technical-kb` skill instead.

## License

MIT
