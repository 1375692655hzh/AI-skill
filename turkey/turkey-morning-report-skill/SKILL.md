---
name: turkey-morning-report-skill
description: Use when generating a Turkish stock market morning briefing in Chinese, based on the previous trading day's closing review and overnight/ weekend news.
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [turkey, borsa, bist, morning-report, market-briefing, investment]
    related_skills: []
---

# Turkey Morning Report Skill

## Overview

A standalone, agent-agnostic skill for generating a Chinese-language Turkish stock market morning briefing.

The skill is designed to be invoked by any automation tool (Hermes Agent, OpenClaw, Cron, manual CLI). It does not include a push/delivery system — it only produces a finished text file at a documented location. The caller is responsible for deciding when to run it and for distributing the output.

## When to Use

- **推荐运行时间：北京时间 14:30**（土耳其时间 09:30，开盘前 30 分钟）
  - 此时 BloombergHT 已发布当日突发新闻和重点新闻
  - 前一天收盘总结已缓存（如有）
  - 为开盘前提供最新市场动态
- Re-run after holidays, weekends, or major overnight events to capture the latest context.
- Use as a reusable module inside a broader agent workflow or cron scheduler.

Do **not** use this skill for real-time trading signals, options/FX-only reports, or non-Chinese output.

## Inputs the Caller Must Provide

1. **A configured LLM API** that can read Turkish and write Chinese in the requested format. The skill does not bundle a model.
2. **Environment variables** for the chosen LLM provider (see `references/llm_provider_examples.md`).
3. **Python 3.9+** with dependencies from `requirements.txt` (see `SETUP.md`).

The skill is self-contained. A separate Turkey-investment project is **optional** — only needed if you enable `sources.bloomberght_closing.use_project_fetcher`.

## Outputs

- **完整版**：`{output_dir}/{today_date}_daily_briefing_zh.txt`（800–1200 字）
- **简报版**：`{output_dir}/{today_date}_daily_briefing_brief_zh.txt`（200–520 字，【字段】结构化，个股每只一行）
- Default output directory is `output/` (relative to skill directory).
- No WhatsApp, email, or other delivery is performed.

## Run Flow

1. **Resolve target date** in Turkey time (UTC+3, fixed all year).
   - Monday → previous Friday.
   - Tuesday–Friday → previous calendar day.
   - Configured holidays are skipped.
2. **Fetch BloombergHT news** (3 sources):
   - **Closing review** (`Piyasalarda günün özeti`): BIST 100, sectors, forex, gold, oil, crypto.
   - **Breaking news** (`SON DAKİKA`): real-time headlines from BloombergHT main page (geopolitics, OPEC, Trump, Fed, etc.).
   - **Featured news** (`Öne Çıkan Haberler`): analyst reports, institutional views, major corporate events.
3. **Fetch supplementary news** (optional).
   - Search API: Tavily (default), Serper, Firecrawl.
   - X search: if the caller has a Grok-capable tool and enables it.
4. **Build prompt** from the template and the collected data.
5. **Call the configured LLM** with strict format instructions.
6. **Validate output**.
7. **Validate output** (full + brief).
8. **Write files** and return paths.

Brief format (one field per line):

```
【土耳其股市早报简报 — {date}】
指数：...
汇率：...
驱动：...
个股：...
板块：...
操作：...
风险：...
```

## News Sources

### BloombergHT (Primary Source)

The skill automatically fetches 3 types of content from BloombergHT:

| Source | URL | Content | Timing |
|--------|-----|---------|--------|
| Closing review | RSS + article | BIST 100, sectors, forex, gold, oil, crypto | TR ~18:30 |
| Breaking news | `bloomberght.com/borsa` | SON DAKİKA headlines (geopolitics, OPEC, Trump, Fed) | Real-time |
| Featured news | `bloomberght.com/borsa` | Öne Çıkan Haberler (analyst reports, institutional views) | Real-time |

### Search API (Optional Supplement)

Three search APIs are supported for additional news coverage:

| API | Key Env Var | Strengths |
|-----|-------------|-----------|
| **Tavily** | `TAVILY_API_KEY` | Returns full content, best for direct LLM use |
| **Serper** | `SERPER_API_KEY` | Fast, mainstream media sources |
| **Firecrawl** | `FIRECRAWL_API_KEY` | Good date filtering, deep scraping |

Configure in `config.json`:

```json
{
  "sources": {
    "news": {
      "search_engine": {
        "primary": "tavily",
        "fallback": ["serper", "firecrawl"],
        "api_keys": {
          "tavily": "${TAVILY_API_KEY}",
          "serper": "${SERPER_API_KEY}",
          "firecrawl": "${FIRECRAWL_API_KEY}"
        }
      }
    }
  }
}
```

### Agent Mode vs API Mode

Two modes are supported, controlled by `sources.news.mode` in `config.json`:

#### Mode 1: `agent` (default)

The skill does **not** fetch news itself. The calling agent must pre-fetch results and save them to:

```
{cache_dir}/news_{target_date}.json
```

#### Mode 2: `api`

The skill uses a model API with built-in web search. Set `sources.news.api`:

```json
{
  "sources": {
    "news": {
      "mode": "api",
      "api": {
        "provider": "minimax",
        "model": "MiniMax-M3",
        "api_key": "${MINIMAX_API_KEY}",
        "base_url": "https://api.minimaxi.com/v1",
        "temperature": 0.3
      }
    }
  }
}
```

Supported APIs:

| Provider | Model | Notes |
|----------|-------|-------|
| MiniMax | `MiniMax-M3` | Tested with `https://api.minimaxi.com/v1`. Web search via function tool. |
| OpenAI | `gpt-4o-search-preview` | Requires `web_search_preview` tool. |
| Zhipu | `glm-4-alltools` | Requires `web_search` tool. |

**Do not commit API keys to the skill package.** Read the key from environment variables or an external secrets file.

## Configuration

See `config.json` for the default configuration. Key knobs:

| Key | Purpose |
|-----|---------|
| `output_dir` | Where the finished briefing is saved. |
| `cache_dir` | Where raw fetched articles and search results are cached. |
| `sources.bloomberght_closing` | Enable/disable the BloombergHT closing review fetcher. |
| `sources.news.bloomberght.enabled` | Enable/disable BloombergHT breaking news + featured news. |
| `sources.news.mode` | `agent` (caller fetches) or `api` (skill fetches via model API). |
| `sources.news.search_engine` | Search API configuration (Tavily/Serper/Firecrawl). |
| `sources.news.api` | API configuration for mode `api`. |
| `llm` | Provider, model, base URL, temperature, API key env var. |
| `holidays` | Optional extras only; fixed TR holidays auto-generated (Jun+ includes next year). |
| `brief.enabled` | Generate structured brief version (default `true`). |
| `brief.min_chars` / `brief.max_chars` | Brief length bounds (default 200–520). |

## Format Rules (Enforced by Prompt and Validator)

The briefing must be a single Chinese text file with this structure and style:

- Only `【】` as section headers. No `##`, `===`, `---`, or other Markdown.
- No tables, bullets, emojis, bold/italic markers, or numbered lists.
- Paragraphs only. Numbers and data are embedded in flowing sentences.
- **Line break rule**: Within a `【】` section, if discussing different topics (e.g., different stocks, different sectors, different commodities), separate each topic with a blank line for clarity. Sentences within the same topic remain in a continuous paragraph.
- Total length: 800–1200 Chinese characters.
- Sections:
  1. `【土耳其股市早评 — {today date}】` + one-paragraph core view.
  2. `【国际新闻】` (2–3 items, written as prose).
  3. `【关键个股】` (2–3 stocks, one paragraph each, separated by blank lines).
  4. `【行业板块表现】` (leading/lagging sectors + observation, one paragraph).
  5. `【汇市与大宗商品】` (USD/TRY, EUR/TRY, oil, gold, one paragraph).
  6. `【今日操作参考】` (positioning, levels, avoid-list).
  7. `风险提示：` (one line, not a separate section).

## Example Invocation

From the skill directory:

```bash
pip install -r requirements.txt
export MINIMAX_API_KEY="your-key"
python scripts/generate_briefing.py --config config.json
```

See `SETUP.md` for full deployment instructions across Cursor, Codex, Hermes, OpenClaw, and WorkBuddy.

## Common Pitfalls

1. **Running on a Turkish holiday.** The skill returns a clear holiday message and does not generate a briefing.
2. **BloombergHT article not yet published.** If the previous day's closing review is not yet online, the skill reports missing data and writes a placeholder, rather than fabricating data.
3. **LLM without Turkish capability.** The model must read the Turkish BloombergHT article; otherwise the output will be generic or hallucinated. Verify with the provider first.
4. **Missing API key.** Set `MINIMAX_API_KEY` or `OPENAI_API_KEY` per `config.json`.
5. **Treating output as a push.** This skill only writes a file. The caller must add its own WhatsApp/email/Slack sender if needed.

## Verification Checklist

- [ ] `config.json` points to a valid working directory and output directory.
- [ ] LLM environment variables are exported.
- [ ] Running the skill produces `{output_dir}/{today_date}_daily_briefing_zh.txt` and `{output_dir}/{today_date}_daily_briefing_brief_zh.txt`.
- [ ] The output contains all 6 sections and the risk warning.
- [ ] The output has no tables, emojis, bullets, or Markdown separators.
- [ ] The target date logic is correct for Monday/holiday scenarios.
- [ ] BloombergHT fetch works via RSS or fallback search.

## References

- `references/data_sources.md` — full source list and links.
- `references/date_logic.md` — Turkey market calendar and target-date rules.
- `references/llm_provider_examples.md` — provider configuration examples.
- `templates/morning_briefing_template.txt` — example output style.
