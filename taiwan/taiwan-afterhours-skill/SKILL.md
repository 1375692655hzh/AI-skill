---
name: taiwan-afterhours-skill
description: Use when generating a Taiwan (TWSE) after-hours institutional note in Chinese — official TWSE/TAIFEX collect, digest checks, then LLM compose.
version: 1.0.0
author: AI-skills-git
license: MIT
metadata:
  hermes:
    tags: [taiwan, twse, taifex, afterhours, market-briefing]
    related_skills: [taiwan-premarket-skill]
---

# Taiwan After-Hours Report Skill

## Overview

Standalone skill that runs the original **taiwan-equity-daily** after-hours SOP:

1. Collect TWSE (rwd) + TAIFEX futures OI  
2. Closed-loop checks → `digest.json`  
3. Build data brief → LLM compose → markdown report  

No WhatsApp push is included (produce files only; caller distributes).

## When to Use

- **Recommended: Taiwan time ~17:00+** on trading days (after T86 / margins settle; script can wait on T86).
- Keywords: 台股盘后 / 盘后内参 / Taiwan after-hours.

## Inputs

1. Python 3.11+ and `requirements.txt`
2. Network access to `twse.com.tw` and `taifex.com.tw`
3. LLM API (MiniMax / OpenAI-compatible) via `config.json`

Self-contained: default `data/` and `output/` live inside this skill directory. No other skill required.

## Outputs

- `{output_dir}/{date}/台股盘后内参_{date}.md`
- `{output_dir}/{date}/_数据简报_afterhours.md` (audit)
- `{data_dir}/{date}/digest.json` + raw JSON
- `{data_dir}/{date}/盘前部署handoff_供次日早评.md` (written locally; optional for other tools)

## Run Flow

1. Resolve Taiwan (UTC+8) target trading day  
2. `run_afterhours.py` — TWSE full pull, T86 wait, TAIFEX, `analyze`, `inst_streak`, `handoff`  
3. `compose_report.py` — brief + STYLE discipline prompt → LLM  
4. Lexicon scan + mechanical postprocess → write markdown  

Fallback (optional): `python run_fallback.py after [YYYY-MM-DD]` (cnyes only, no LLM).

## Configuration

See `config.example.json`. Critical keys:

| Key | Purpose |
|-----|---------|
| `data_dir` | Local inventory (default `data`) |
| `output_dir` | Finished reports (default `output`) |
| `llm.*` | Provider / model / `api_key_env` |
| `holidays` | Extra closed days `YYYY-MM-DD` |

## Data Discipline

- Date gate on every source; no fabricated numbers  
- Close / institutional closed-loop checks  
- Silent degrade when a field is unavailable  

Details: original README discipline + `STYLE.md`.
