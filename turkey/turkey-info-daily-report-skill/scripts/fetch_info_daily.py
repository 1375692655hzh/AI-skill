#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch Info Yatirim daily bulletin (Günlük Bülten)."""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
LANDING_URL = "https://infoyatirim.com/arastirma/gunluk-bulten"
FALLBACK_URL = LANDING_URL

# Shared session with retry/backoff. Info Yatirim's TLS stack frequently emits
# SSL EOF / 5xx under load; without retries the whole skill gen_fails.
_SESSION = requests.Session()
_RETRY = Retry(
    total=4,
    backoff_factor=1.5,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset({"GET", "HEAD"}),
    raise_on_status=False,
)
_SESSION.mount("https://", HTTPAdapter(max_retries=_RETRY))
_SESSION.mount("http://", HTTPAdapter(max_retries=_RETRY))
_SESSION.headers.update(HEADERS)


def _get(url: str, *, timeout: float = 40.0) -> Optional[requests.Response]:
    """GET with retry/backoff and SSL tolerance. Returns None on hard failure."""
    try:
        resp = _SESSION.get(url, timeout=timeout)
        return resp
    except (requests.RequestException, OSError) as exc:
        print(f"Warning: Info Yatirim GET failed for {url}: {exc}", file=sys.stderr)
        return None


def _slug_for_date(d: date) -> str:
    return f"{d.day:02d}{d.month:02d}{d.year}"


def _find_archive_link(target_date: date) -> Optional[str]:
    needle = f"gunluk-bulten-{_slug_for_date(target_date)}"
    for page in range(1, 4):
        url = f"{LANDING_URL}?page={page}" if page > 1 else LANDING_URL
        resp = _get(url)
        if resp is None:
            return None
        resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if needle in href:
                return href if href.startswith("http") else f"https://infoyatirim.com{href}"
    return None


def _find_bulletin_uuid(target_date: date) -> tuple[Optional[str], Optional[str]]:
    archive_url = _find_archive_link(target_date)
    archive_label = None
    if archive_url:
        resp = _get(archive_url)
        if resp is not None:
            resp.encoding = "utf-8"
            archive_label = resp.text
            for m in re.finditer(r"/Content/Bulletin/([0-9a-fA-F-]{36})\.html", resp.text):
                return m.group(1), archive_label

    resp = _get(LANDING_URL)
    if resp is None:
        return None, None
    resp.encoding = "utf-8"
    archive_label = resp.text

    for m in re.finditer(r"/Content/Bulletin/([0-9a-fA-F-]{36})\.html", resp.text):
        return m.group(1), archive_label

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        for script in soup.find_all("script"):
            text = script.get_text() or script.string or ""
            for m in re.finditer(r"/Content/Bulletin/([0-9a-fA-F-]{36})\.html", text):
                return m.group(1), archive_label
    except Exception:
        pass
    return None, archive_label


def fetch_bulletin_content(uuid: str, archive_label: Optional[str] = None) -> str:
    url = f"https://cdn.infoyatirim.com/Content/Bulletin/{uuid}.html"
    resp = _get(url)
    if resp is None:
        return ""
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")
    for s in soup(["script", "style", "nav", "footer"]):
        s.decompose()
    body = soup.get_text("\n", strip=True)
    label = ""
    if archive_label:
        m = re.search(
            r"(\d{1,2}\s+[a-zA-ZğüşöçıİĞÜŞÖÇ]+\s+\d{4})\s+Günlük Bülteni",
            archive_label,
            re.I,
        )
        if m:
            label = m.group(0)
    text = f"{label}\n{body}" if label else body
    return "\n".join(line for line in text.splitlines() if line.strip())


def fetch_info_daily(
    target_date: date,
    cache_dir: Path,
    *,
    workdir: Optional[Path] = None,
    use_project_fetcher: bool = False,
) -> dict:
    cache_file = cache_dir / f"info_daily_{target_date.isoformat()}.json"
    if cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        if cached.get("content"):
            return cached

    if use_project_fetcher and workdir:
        from fetch_via_project import fetch_info_via_project

        project_result = fetch_info_via_project("info-daily", target_date, workdir)
        if project_result.get("ok"):
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(project_result, ensure_ascii=False, indent=2), encoding="utf-8")
            return project_result

    uuid, archive_label = _find_bulletin_uuid(target_date)
    content = fetch_bulletin_content(uuid, archive_label) if uuid else ""

    result = {
        "ok": bool(uuid and content),
        "reason": "ok" if uuid and content else "not_found",
        "target_date": target_date.isoformat(),
        "uuid": uuid or "",
        "url": f"https://cdn.infoyatirim.com/Content/Bulletin/{uuid}.html" if uuid else "",
        "fallback_url": FALLBACK_URL,
        "content": content,
        "fetch_source": "direct",
    }

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    cache = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".cache/turkey-info-daily-report")
    r = fetch_info_daily(target, cache)
    print(json.dumps(r, ensure_ascii=False, indent=2)[:3000])
