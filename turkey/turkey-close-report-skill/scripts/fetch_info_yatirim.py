#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch Info Yatirim daily bulletin and technical bulletin."""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup


HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


LANDING_PAGES = {
    "daily": "https://infoyatirim.com/arastirma/gunluk-bulten",
    "technical": "https://infoyatirim.com/arastirma/teknik-bulten",
}


def _slug_for_date(d: date) -> str:
    return f"{d.day:02d}{d.month:02d}{d.year}"


def _find_archive_link(landing_url: str, target_date: date) -> Optional[str]:
    """Find the per-day archive link from the landing page pagination."""
    needle = f"bulten-{_slug_for_date(target_date)}"
    for page in range(1, 4):
        url = f"{landing_url}?page={page}" if page > 1 else landing_url
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.encoding = "utf-8"
        except Exception as exc:
            print(f"Warning: Info Yatirim archive page failed: {exc}", file=sys.stderr)
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if needle in href:
                return href if href.startswith("http") else f"https://infoyatirim.com{href}"
    return None


def _find_bulletin_uuid(landing_url: str, target_date: date) -> tuple[Optional[str], Optional[str]]:
    """
    Find the bulletin UUID and the archive page URL/label.
    Returns (uuid, archive_label_or_url).
    """
    archive_url = _find_archive_link(landing_url, target_date)
    archive_label = None
    if archive_url:
        try:
            resp = requests.get(archive_url, headers=HEADERS, timeout=20)
            resp.encoding = "utf-8"
            # Use archive page title/label for date verification
            archive_label = resp.text
            for m in re.finditer(r"/Content/Bulletin/([0-9a-fA-F-]{36})\.html", resp.text):
                return m.group(1), archive_label
        except Exception as exc:
            print(f"Warning: Info Yatirim archive page content failed: {exc}", file=sys.stderr)

    # Fallback: latest from landing page
    try:
        resp = requests.get(landing_url, headers=HEADERS, timeout=20)
        resp.encoding = "utf-8"
        archive_label = resp.text
    except Exception as exc:
        print(f"Warning: Info Yatirim landing page failed: {exc}", file=sys.stderr)
        return None, None

    for m in re.finditer(r"/Content/Bulletin/([0-9a-fA-F-]{36})\.html", resp.text):
        return m.group(1), archive_label

    try:
        soup = BeautifulSoup(resp.text, "lxml")
        for script in soup.find_all("script"):
            text = script.get_text() or script.string or ""
            for m in re.finditer(r"/Content/Bulletin/([0-9a-fA-F-]{36})\.html", text):
                return m.group(1), archive_label
    except Exception:
        pass
    return None, archive_label


def fetch_bulletin_content(uuid: str, archive_label: Optional[str] = None) -> str:
    url = f"https://cdn.infoyatirim.com/Content/Bulletin/{uuid}.html"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")
        for s in soup(["script", "style", "nav", "footer"]):
            s.decompose()
        body = soup.get_text("\n", strip=True)
        # Prepend a clean date label from the archive page for date verification
        label = ""
        if archive_label:
            # Extract the title-like date string if present
            m = re.search(r"(\d{1,2}\s+[a-zA-ZğüşöçıİĞÜŞÖÇ]+\s+\d{4})\s+Teknik Bülteni|(\d{1,2}\s+[a-zA-ZğüşöçıİĞÜŞÖÇ]+\s+\d{4})\s+Günlük Bülteni", archive_label, re.I)
            if m:
                label = m.group(0)
        text = f"{label}\n{body}" if label else body
        return "\n".join(line for line in text.splitlines() if line.strip())
    except Exception as exc:
        print(f"Warning: Info Yatirim bulletin content failed: {exc}", file=sys.stderr)
    return ""


def fetch_info_yatirim(target_date: date, cache_dir: Path) -> dict:
    cache_file = cache_dir / f"info_yatirim_{target_date.isoformat()}.json"
    if cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        if cached.get("daily", {}).get("content") and cached.get("technical", {}).get("content"):
            return cached

    daily_uuid, daily_label = _find_bulletin_uuid(LANDING_PAGES["daily"], target_date)
    technical_uuid, technical_label = _find_bulletin_uuid(LANDING_PAGES["technical"], target_date)

    daily_content = fetch_bulletin_content(daily_uuid, daily_label) if daily_uuid else ""
    technical_content = fetch_bulletin_content(technical_uuid, technical_label) if technical_uuid else ""

    result = {
        "ok": bool(daily_uuid) or bool(technical_uuid),
        "target_date": target_date.isoformat(),
        "daily": {
            "uuid": daily_uuid or "",
            "url": f"https://cdn.infoyatirim.com/Content/Bulletin/{daily_uuid}.html" if daily_uuid else "",
            "content": daily_content,
        },
        "technical": {
            "uuid": technical_uuid or "",
            "url": f"https://cdn.infoyatirim.com/Content/Bulletin/{technical_uuid}.html" if technical_uuid else "",
            "content": technical_content,
        },
    }

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    cache = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".cache/turkey-close-report")
    r = fetch_info_yatirim(target, cache)
    print(json.dumps(r, ensure_ascii=False, indent=2)[:2000])
