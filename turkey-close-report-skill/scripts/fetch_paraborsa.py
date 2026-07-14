#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch Paraborsa broker close-of-day commentaries."""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

import requests
from bs4 import BeautifulSoup


HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Priority order for broker commentary (lowercase slugs)
PRIORITY_BROKERS = ["destek-yatirim", "bizim-yatirim", "bulls", "info-yatirim", "integral-yatirim"]


def turkish_month_to_int(month: str) -> int:
    months = {
        "ocak": 1, "subat": 2, "mart": 3, "nisan": 4, "mayis": 5, "haziran": 6,
        "temmuz": 7, "agustos": 8, "eylul": 9, "ekim": 10, "kasim": 11, "aralik": 12,
    }
    return months.get(month.lower().replace("ı", "i").replace("ş", "s").replace("ç", "c").replace("ğ", "g").replace("ü", "u").replace("ö", "o"), 1)


def slugify_date(d: date) -> str:
    """Return date slug like '8-07-2026' for Paraborsa."""
    return f"{d.day}-{d.month:02d}-{d.year}"


def fetch_api_post(broker_slug: str, target_date: date) -> Optional[dict]:
    """Try WP JSON API by slug."""
    date_slug = slugify_date(target_date)
    slug = f"borsa-yorumu-{broker_slug}-{date_slug}"
    url = f"https://www.paraborsa.net/wp-json/wp/v2/posts?slug={slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        data = resp.json()
        if data:
            post = data[0]
            return {
                "title": post.get("title", {}).get("rendered", ""),
                "url": post.get("link", ""),
                "content": BeautifulSoup(post.get("content", {}).get("rendered", ""), "lxml").get_text("\n", strip=True),
            }
    except Exception as exc:
        print(f"Warning: Paraborsa API failed for {broker_slug}: {exc}", file=sys.stderr)
    return None


def fetch_homepage_links(target_date: date) -> List[dict]:
    """Fetch today's broker commentary links from homepage."""
    try:
        resp = requests.get("https://www.paraborsa.net/", headers=HEADERS, timeout=20)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as exc:
        print(f"Warning: Paraborsa homepage failed: {exc}", file=sys.stderr)
        return []

    results = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.search(r"borsa-yorumu", href, re.I):
            continue
        title = a.get_text(strip=True)
        if not title:
            continue
        # Try to extract date from URL or title
        m = re.search(r"borsa-yorumu-[^/]+-(\d{1,2})-(\d{1,2})-(\d{4})/", href)
        if m:
            d, mon, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                link_date = date(y, mon, d)
            except ValueError:
                continue
            if link_date == target_date:
                results.append({"title": title, "url": href, "content": ""})
    return results


def extract_article_content(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")
        content = soup.find("article") or soup.find("div", class_=re.compile("content|entry")) or soup.find("main")
        if content:
            for s in content(["script", "style", "nav", "footer"]):
                s.decompose()
            return content.get_text("\n", strip=True)
        return soup.get_text("\n", strip=True)
    except Exception as exc:
        print(f"Warning: Paraborsa article extraction failed: {exc}", file=sys.stderr)
    return ""


def fetch_paraborsa(target_date: date, cache_dir: Path) -> dict:
    cache_file = cache_dir / f"paraborsa_{target_date.isoformat()}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    # Try homepage first to get all candidates
    homepage_links = fetch_homepage_links(target_date)
    candidates = {}

    # Fill content for homepage links and identify broker
    for item in homepage_links:
        broker_match = re.search(r"borsa-yorumu-([^/]+?)-\d{1,2}-\d{1,2}-\d{4}", item["url"])
        if not broker_match:
            continue
        broker_slug = broker_match.group(1)
        if broker_slug not in candidates:
            item["content"] = extract_article_content(item["url"])
            candidates[broker_slug] = item

    # If homepage missing, try API for priority brokers
    for broker in PRIORITY_BROKERS:
        if broker in candidates:
            continue
        post = fetch_api_post(broker, target_date)
        if post:
            candidates[broker] = post

    # Sort by priority
    sorted_items = []
    for broker in PRIORITY_BROKERS:
        if broker in candidates:
            sorted_items.append(candidates[broker])
    for broker, item in candidates.items():
        if broker not in PRIORITY_BROKERS:
            sorted_items.append(item)

    selected = sorted_items[0] if sorted_items else None

    result = {
        "ok": selected is not None,
        "target_date": target_date.isoformat(),
        "selected": selected if selected else {},
        "candidates": [
            {"title": c.get("title", ""), "url": c.get("url", "")} for c in sorted_items[:3]
        ],
    }

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    cache = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".cache/turkey-close-report")
    r = fetch_paraborsa(target, cache)
    print(json.dumps(r, ensure_ascii=False, indent=2)[:3000])
