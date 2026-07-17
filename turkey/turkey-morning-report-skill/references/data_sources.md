# Data Sources

This skill uses the following sources. All are configurable in `config.json`.

## Primary Source: BloombergHT Detailed Closing Review

| Field | Value |
|-------|-------|
| Source | BloombergHT |
| Article | Piyasalarda günün özeti (Detailed closing summary) |
| Typical publish time (TR) | ~18:30 |
| Typical publish time (Beijing) | ~23:30 |
| RSS | `https://www.bloomberght.com/rss` |
| Borsa section | `https://www.bloomberght.com/borsa` |
| Article title patterns | `Piyasalarda günün özeti: {date} ...` or `Piyasa özeti: {date} ...` |
| Article URL example | `https://www.bloomberght.com/piyasalarda-gunun-ozeti-10-temmuz-2026-bist-100-de-degisimler-ve-doviz-fiyatlari-pkh-3782616` |

Fetcher strategy:
1. Download RSS feed.
2. Find an item whose title matches the patterns and whose date matches the resolved target date.
3. If not found, run a web search for the title + date and extract the article URL.
4. Extract the article body using a generic HTML reader (requests + BeautifulSoup or an MCP reader).
5. Cache raw HTML and extracted text.

## Supplementary Sources

### Web Search

Used by default. Example queries:

- `Turkey BIST stock market {target_date}`
- `USD TRY exchange rate {target_date}`
- `Turkey economic news {target_date}`
- `Federal Reserve Europe Turkey market {target_date}`
- `Borsa Istanbul latest news {target_date}`

The skill calls the search tool, fetches the top result pages, and summarizes them with the LLM or extracts key snippets.

### X Search (Optional)

Requires a Grok-like X search tool. If enabled, the skill queries:

- `Borsa Istanbul today`
- `Turkey stock market today`
- `USD TRY today`

If the tool is unavailable, the skill falls back to web search only.

## Legacy / Optional Sources

These are supported by the optional `fetch.py` in a Turkey-investment project. Enable `sources.bloomberght_closing.use_project_fetcher: true` and set `workdir` to that project path.

Default output directory: `output/`.

| Source | Name in `fetch.py` | Typical TR time |
|--------|-------------------|-----------------|
| Foreks opening brief | `morning` | 09:57 |
| Info Yatırım daily bulletin | `info-daily` | ~11:00 |
| Info Yatırım technical bulletin | `info-technical` | ~12:00 |
| Paraborsa broker commentary | `paraborsa` | ~16:30 |
| Foreks fast close | `foreks-close` | ~18:16 |
| BloombergHT detailed close | `closing` | ~18:30 |

This skill focuses on `closing` (BloombergHT) as the primary source because the user specified the detailed closing review as the main input.

## Output

Only one file is produced:

```
{output_dir}/{today_date}_daily_briefing_zh.txt
```

Default output directory: `output/`.

No delivery/push is performed.
