---
name: turkey-aa-morning-briefing-skill
description: Fetches the daily Anadolu Agency English Morning Briefing full text, optionally translates the body to Chinese via LLM, records publish/update timestamps, and moves NEWS IN BRIEF to the bottom. Use when the user asks for AA morning briefing, Anadolu morning briefing scrape, or daily AA world news digest.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [anadolu, aa, morning-briefing, news, world-news, scrape]
    related_skills: [turkey-morning-report-skill, turkey-info-daily-report-skill]
---

# Turkey AA Morning Briefing Skill

## Overview

Standalone skill that:

1. **Discovers** today's (or a forced date's) AA English *Morning Briefing* article
2. **Fetches** the full original body
3. **Records** publish / update time (TR UTC+3 and Beijing UTC+8)
4. **Reorders** only one thing: put **NEWS IN BRIEF** at the **bottom** (wording unchanged)
5. **Optionally translates** the body to Simplified Chinese (`translate.enabled`, default true; metadata header stays English). Use `--no-llm` to keep English.
6. Writes a plain-text file

Example source page: [Morning Briefing: July 16, 2026](https://www.aa.com.tr/en/world/morning-briefing-july-16-2026/3999751)

## 开箱即用

给同事用时，**复制整个 `turkey-aa-morning-briefing-skill` 目录即可**，不依赖其他项目。

| 必需 | 说明 |
|------|------|
| Python 3.9+ | `pip install -r requirements.txt` |
| 网络 | 能访问 `aa.com.tr` |
| `config.json` | 目录已附带；也可 `cp config.example.json config.json` |

```bash
cd turkey-aa-morning-briefing-skill
pip install -r requirements.txt
python scripts/generate_aa_morning_briefing.py --config config.json
```

## When to Use

- 每日抓取 Anadolu Agency English Morning Briefing 全文
- 需要确认源站发布/更新时间
- 需要把 NEWS IN BRIEF 固定排在文末

Do **not** use for Turkish BloombergHT 早报（那是 `turkey-morning-report-skill`）。

## Recommended Schedule（推荐执行时间）

源站时间为 **土耳其时间 TR = UTC+3**（全年无夏令时）。  
近 14 日实测（2026-07-03～07-16）：成功 11/14；发布窗口 **TR 06:44–08:44**（北京 **11:44–13:44**），均值约 TR 07:46 / 北京 12:46。  
周末也常更新；个别工作日可能停更；土耳其假日（如 07-15）通常无稿。

| 项目 | 值 |
|------|-----|
| 源站发布窗口 (TR) | 06:45–08:45 |
| 源站发布窗口 (北京) | 11:45–13:45 |
| **Cron 首发 (北京)** | **12:10** |
| 重试 | 12:40、13:10、13:40 |
| 兜底 | **14:10** |
| 周末 | **要跑**（近两周周末 4/4 有稿） |
| 土耳其节假日 | 可跳过（`skip_holidays: true`） |

```
12:10, 12:40, 13:10, 13:40  → 首发循环（含周末）
14:10                         → 兜底
```

## Data Source

| Source | URL |
|--------|-----|
| Article pattern | `https://www.aa.com.tr/en/world/morning-briefing-{month}-{day}-{year}/{id}` |
| Search discovery | `https://www.aa.com.tr/en/search?s=Morning+Briefing` |
| World RSS | `https://www.aa.com.tr/en/rss/default?cat=world` |
| World page | `https://www.aa.com.tr/en/world` |

Discovery order: **search → world RSS → world page**. Optional `sources.aa_morning_briefing.force_url` overrides discovery.

## Outputs

| 文件 | 说明 |
|------|------|
| `output/{date}_aa_morning_briefing.txt` | 元数据头 + 全文（NEWS IN BRIEF 在底部） |
| `.cache/turkey-aa-morning-briefing/aa_morning_briefing_{date}.json` | 抓取缓存（含 original / reordered） |

### Output layout

```
Morning Briefing: July 16, 2026

Source: https://www.aa.com.tr/en/world/...
Target date: 2026-07-16
Author: ...
Page date: 16 July 2026
Page update label: Update: 16 July 2026
Published (TR UTC+3): ...
Published (Beijing UTC+8): ...
Modified (TR UTC+3): ...
RSS pubDate: ...
Note: NEWS IN BRIEF section moved to bottom (content unchanged).

========================================================================

(intro)
TOP STORIES
...
BUSINESS & ECONOMY
...
SPORTS
...
NEWS IN BRIEF
...
```

## Run Flow

1. Resolve target date (TR calendar; weekend/holiday → previous publish day)
2. Discover article URL for `morning-briefing-{month}-{day}-{year}`
3. Fetch HTML → extract body from page payload → parse meta/RSS times
4. Reorder: move **NEWS IN BRIEF** to bottom
5. Validate ordering → write output file

## Configuration

| Key | Purpose |
|-----|---------|
| `output_dir` | Finished text location |
| `cache_dir` | Raw JSON cache |
| `target_date` | `auto` or `YYYY-MM-DD` |
| `skip_weekend` | Skip Sat/Sun (default `false`，周末也常发) |
| `skip_holidays` | Skip `holidays` list (default `true`) |
| `sources.aa_morning_briefing.force_url` | Pin a specific article URL |
| `holidays` | Optional extras only; fixed TR holidays auto-generated (Jun+ includes next year) |

## Example

```bash
# Today (TR)
python scripts/generate_aa_morning_briefing.py --config config.json

# Historical date
python scripts/generate_aa_morning_briefing.py --config config.json --force-date 2026-07-16

# Direct URL
python scripts/generate_aa_morning_briefing.py --config config.json --force-url "https://www.aa.com.tr/en/world/morning-briefing-july-16-2026/3999751"

# Ignore cache
python scripts/generate_aa_morning_briefing.py --config config.json --force-date 2026-07-16 --force-refresh
```

## Common Pitfalls

1. **Too early** — before ~08:30 TR the article may not exist yet; use retry cron.
2. **Missing day** — 个别日期源站无稿（近两周如 07-07/08/15）；假日可配置跳过，周末默认仍抓。
3. **Slug day is unpadded** — `july-9-2026` not `july-09-2026` (handled by skill).
4. **Only reorder NEWS IN BRIEF** — do not rewrite or translate body text.

## Verification Checklist

- [ ] `pip install -r requirements.txt` succeeds
- [ ] `--force-date 2026-07-16` produces `output/2026-07-16_aa_morning_briefing.txt`
- [ ] Header contains Published (TR) and Published (Beijing)
- [ ] Body contains TOP STORIES / BUSINESS & ECONOMY / SPORTS
- [ ] **NEWS IN BRIEF is the last section**
