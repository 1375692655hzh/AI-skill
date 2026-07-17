#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch supplementary news from BloombergHT, web_search, and optional x_search."""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from search_api import SearchAPI
from fetch_bloomberght_closing import fetch_all_news as fetch_bloomberght_all


def _format_queries(queries: list[str], target_date: date) -> list[str]:
    return [q.format(target_date=target_date.isoformat(), date=target_date.isoformat()) for q in queries]


def _resolve_api_key(value: Optional[str]) -> Optional[str]:
    """Resolve ${ENV_VAR} or ${ENV_VAR:default} syntax from environment."""
    if not value or not isinstance(value, str):
        return value
    import re
    match = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}", value)
    if not match:
        return value
    env_var, default = match.groups()
    return os.environ.get(env_var, default if default is not None else value)


def search_with_api(
    queries: list[str],
    cache_dir: Path,
    target_date: date,
    api_config: dict,
) -> list[dict]:
    """Use a model API with web search capability to fetch news summaries."""
    api_key = _resolve_api_key(api_config.get("api_key"))
    if not api_key:
        return [{"title": "API search not configured", "url": "", "snippet": "Set news.api.api_key (or env var) in config.json.", "query": ""}]
    api = SearchAPI(
        provider=api_config.get("provider", "minimax"),
        model=api_config.get("model", "MiniMax-M3"),
        api_key=api_key,
        base_url=api_config.get("base_url", "https://api.minimaxi.com/v1"),
        temperature=api_config.get("temperature", 0.3),
    )
    results = []
    for q in queries:
        try:
            summary = api.search(q)
            if summary:
                results.append({
                    "title": f"News summary: {q}",
                    "url": "",
                    "snippet": summary,
                    "query": q,
                })
        except Exception as e:
            results.append({
                "title": f"Search error for: {q}",
                "url": "",
                "snippet": str(e),
                "query": q,
            })
    return results


def fetch_news(
    target_date: date,
    cache_dir: Path,
    news_cfg: dict,
    *,
    workdir: Path | None = None,
    closing_cfg: dict | None = None,
) -> dict:
    """
    Fetch overnight/weekend news from multiple sources:
    1. BloombergHT (closing review + breaking news + featured news)
    2. Web search (via search API)
    3. X search (optional)
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"news_{target_date.isoformat()}.json"

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            closing = (cached.get("bloomberght") or {}).get("closing_review") or {}
            if cached.get("ok") and closing.get("ok"):
                return cached
        except Exception:
            pass

    mode = news_cfg.get("mode", "agent")
    bloomberght_enabled = news_cfg.get("bloomberght", {}).get("enabled", True)
    web_search_enabled = news_cfg.get("web_search", {}).get("enabled", True)
    x_search_enabled = news_cfg.get("x_search", {}).get("enabled", False)

    # 1. Fetch BloombergHT news (closing + breaking + featured)
    bloomberght_results = {}
    bloomberght_cache = cache_dir / f"bloomberght_all_{target_date.isoformat()}.json"
    
    if bloomberght_cache.exists():
        try:
            bloomberght_results = json.loads(bloomberght_cache.read_text(encoding="utf-8"))
            closing = bloomberght_results.get("closing_review") or {}
            if bloomberght_results.get("ok") and closing.get("ok"):
                print("Using cached BloombergHT news", file=sys.stderr)
            else:
                bloomberght_results = {}
        except Exception:
            bloomberght_results = {}
    
    if not bloomberght_results and bloomberght_enabled:
        try:
            print("Fetching BloombergHT news...", file=sys.stderr)
            bloomberght_results = fetch_bloomberght_all(
                target_date,
                cache_dir,
                workdir=workdir,
                closing_cfg=closing_cfg,
            )
        except Exception as e:
            print(f"BloombergHT fetch failed: {e}", file=sys.stderr)
            bloomberght_results = {"ok": False, "error": str(e)}

    # 2. Fetch web search results
    raw_queries = news_cfg.get("web_search", {}).get("queries", [
        "Turkey BIST stock market {target_date}",
        "USD TRY exchange rate {target_date}",
        "Turkey economic news {target_date}",
        "Borsa Istanbul latest news {target_date}",
    ])
    queries = _format_queries(raw_queries, target_date)

    x_queries = []
    if x_search_enabled:
        x_raw = news_cfg.get("x_search", {}).get("queries", [
            "Borsa Istanbul today",
            "Turkey stock market today",
            "USD TRY today",
        ])
        x_queries = _format_queries(x_raw, target_date)

    web_results = []
    x_results = []

    if web_search_enabled:
        if mode == "api":
            api_config = news_cfg.get("api")
            if api_config:
                web_results = search_with_api(queries, cache_dir, target_date, api_config)
            else:
                web_results = [{"title": "API search not configured", "url": "", "snippet": "Set news.api.provider, model, api_key, and base_url in config.json.", "query": ""}]

    result = {
        "ok": True,
        "target_date": target_date.isoformat(),
        "mode": mode,
        "bloomberght": bloomberght_results,
        "web_search": {
            "enabled": web_search_enabled,
            "queries": queries,
            "results": web_results,
        },
        "x_search": {
            "enabled": x_search_enabled,
            "queries": x_queries,
            "results": x_results,
        },
        "total_items": (
            bloomberght_results.get("total_items", 0) +
            len(web_results) +
            len(x_results)
        ),
        "note": (
            "Agent mode: the caller should pre-fetch web/x_search results and save them to "
            f"{cache_file} before running this skill. "
            "API mode: set news.api to use a model API with built-in web search."
        ),
    }
    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    import sys

    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    cache = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".cache/turkey-morning-report")
    cfg = {
        "mode": "agent",
        "web_search": {"enabled": True, "queries": []},
        "x_search": {"enabled": False, "queries": []},
    }
    r = fetch_news(target, cache, cfg)
    print(json.dumps(r, ensure_ascii=False, indent=2))
