---
name: taiwan-premarket-skill
description: Use when generating a Taiwan (TWSE) pre-market morning note in Chinese — prior-day inventory, OpenD ADR/SOXX, cnyes premarket wrap, then LLM compose.
version: 1.0.0
author: AI-skills-git
license: MIT
metadata:
  hermes:
    tags: [taiwan, twse, premarket, morning-briefing, adr]
    related_skills: [taiwan-afterhours-skill]
---

# Taiwan Premarket Report Skill

## Overview

Standalone skill that runs the original **taiwan-equity-daily** premarket SOP:

1. Ensure T-1 inventory in local `data/` (auto-collect inside this skill if missing)  
2. OpenD (optional) ADR / SOX members / oil-gold + premium  
3. cnyes 〈台股盤前要聞〉 + night futures when available  
4. Read prior-day handoff if present → `premarket_digest.json` → LLM compose  

Self-contained: does **not** require installing `taiwan-afterhours-skill`.

## When to Use

- **Recommended: Taiwan time ~08:40** on trading days.
- Keywords: 台股盘前 / 盘前早评 / Taiwan premarket.

## Inputs

1. Python 3.11+ and `requirements.txt`
2. Optional: Futu OpenD gateway + `opend.futu_python` in config
3. LLM API via `config.json`

## Outputs

- `{output_dir}/{date}/台股盘前早评_{date}.md`
- `{output_dir}/{date}/_数据简报_premarket.md`
- `{data_dir}/{date}/premarket_digest.json`

## Run Flow

1. Resolve Taiwan target date  
2. `run_premarket.py` → `premarket_digest.json`  
3. `compose_report.py` premarket prompt (STYLE) → LLM  
4. Write markdown  

Without OpenD, ADR/SOXX layers degrade silently; cnyes narrative may still run.

Fallback: `python run_fallback.py before [YYYY-MM-DD]`.

## Configuration

| Key | Purpose |
|-----|---------|
| `data_dir` | Local inventory (default `data`) |
| `opend.futu_python` | Python that has `futu-api` (empty = skip OpenD) |
| `llm.*` | Same as turkey skills |
