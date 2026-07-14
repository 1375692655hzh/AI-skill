#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch BloombergHT closing review + breaking news + featured articles."""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from bht_closing_fetcher import (
    BASE,
    HEADERS,
    fetch_closing_review as _fetch_closing_review,
)

BORSA_URL = f"{BASE}/borsa"


def fetch_breaking_news(url: str = BORSA_URL) -> List[Dict[str, str]]:
    """Fetch SON DAKİKA headlines from BloombergHT /borsa."""
    items: list[dict[str, str]] = []
    try:
        resp = requests.get(url, timeout=20, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        son_dakika_header = soup.find(string=re.compile("SON DAKİKA", re.I))
        if not son_dakika_header:
            return items

        parent = son_dakika_header.find_parent()
        if not parent:
            return items

        seen_titles: set[str] = set()
        for link in parent.find_all_next("a", limit=30):
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if not title or len(title) < 20 or title in seen_titles:
                continue
            if href.startswith("/") and not href.startswith("/sondakika"):
                continue
            items.append({
                "title": title,
                "url": urljoin(BASE, href),
            })
            seen_titles.add(title)
            if len(items) >= 10:
                break
    except Exception as e:
        print(f"Breaking news fetch failed: {e}", file=sys.stderr)
    return items


def fetch_featured_news(url: str = BORSA_URL) -> List[Dict[str, str]]:
    """Fetch Öne Çıkan Haberler from BloombergHT /borsa."""
    items: list[dict[str, str]] = []
    try:
        resp = requests.get(url, timeout=20, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        featured_header = soup.find(string=re.compile("Öne Çıkan", re.I))
        if not featured_header:
            return items

        parent = featured_header.find_parent()
        if not parent:
            return items

        seen_titles: set[str] = set()
        for link in parent.find_all_next("a", limit=30):
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if not title or len(title) < 20 or title in seen_titles:
                continue
            if href.startswith("/"):
                href = urljoin(BASE, href)
            elif not href.startswith("http"):
                continue
            items.append({"title": title, "url": href})
            seen_titles.add(title)
            if len(items) >= 10:
                break
    except Exception as e:
        print(f"Featured news fetch failed: {e}", file=sys.stderr)
    return items


def fetch_all_news(
    target_date: date,
    cache_dir: Path,
    *,
    workdir: Path | None = None,
    closing_cfg: dict | None = None,
) -> Dict:
    """Fetch closing review + breaking + featured news for target_date."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"bloomberght_all_{target_date.isoformat()}.json"
    closing_cfg = closing_cfg or {}

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            closing = cached.get("closing_review") or {}
            if cached.get("ok") and closing.get("ok"):
                return cached
        except Exception:
            pass

    print("Fetching BloombergHT closing review...", file=sys.stderr)
    closing = fetch_closing_review(
        target_date=target_date,
        cache_dir=cache_dir,
        workdir=workdir,
        closing_cfg=closing_cfg,
    )

    print("Fetching breaking news (SON DAKİKA)...", file=sys.stderr)
    breaking = fetch_breaking_news()

    print("Fetching featured news (Öne Çıkan Haberler)...", file=sys.stderr)
    featured = fetch_featured_news()

    result = {
        "ok": True,
        "target_date": target_date.isoformat(),
        "source": "bloomberght",
        "closing_review": closing,
        "breaking_news": breaking,
        "featured_news": featured,
        "total_items": len(breaking) + len(featured) + (1 if closing.get("ok") else 0),
    }
    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def fetch_closing_review(
    target_date: date,
    cache_dir: Path,
    rss_url: str = f"{BASE}/rss",
    *,
    workdir: Path | None = None,
    closing_cfg: dict | None = None,
) -> dict:
    closing_cfg = closing_cfg or {}
    if closing_cfg.get("enabled") is False:
        return {
            "ok": False,
            "target_date": target_date.isoformat(),
            "error": "BloombergHT closing fetch disabled in config.",
            "title": None,
            "url": None,
            "text": None,
            "source": "bloomberght",
        }
    return _fetch_closing_review(
        target_date=target_date,
        cache_dir=cache_dir,
        workdir=workdir,
        rss_url=closing_cfg.get("rss_url", rss_url),
        list_page_url=closing_cfg.get(
            "list_page_url",
            f"{BASE}/tum-piyasa-haberleri",
        ),
        use_project_fetcher=closing_cfg.get("use_project_fetcher", True),
    )


if __name__ == "__main__":
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    cache = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".cache/turkey-morning-report")
    workdir = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else None
    result = fetch_all_news(target, cache, workdir=workdir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
