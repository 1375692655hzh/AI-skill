#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch Info Yatirim daily bulletin and technical bulletin.

Soft dependency for the close report: fail fast (seconds–tens of seconds),
never burn minutes on retries when the site is down.
"""
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

# Soft source: at most one retry (2 attempts total). Listing/landing pages use
# a short timeout; CDN body may use a slightly longer one.
_SESSION = requests.Session()
_RETRY = Retry(
    total=1,
    backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset({"GET", "HEAD"}),
    raise_on_status=False,
)
_SESSION.mount("https://", HTTPAdapter(max_retries=_RETRY))
_SESSION.mount("http://", HTTPAdapter(max_retries=_RETRY))
_SESSION.headers.update(HEADERS)

LIST_TIMEOUT = 12.0
BODY_TIMEOUT = 20.0
# Abandon a bulletin source after this many hard failures/timeouts.
MAX_SOURCE_FAILURES = 2


class _SourceBudget:
    """Track consecutive failures for one Info Yatırım bulletin stream."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.failures = 0
        self.abandoned = False
        self.reason = ""

    def record_fail(self, reason: str) -> None:
        self.failures += 1
        self.reason = reason
        if self.failures >= MAX_SOURCE_FAILURES:
            self.abandoned = True
            print(
                f"Warning: Info Yatirim {self.name} abandoned after "
                f"{self.failures} failures (last={reason})",
                file=sys.stderr,
            )


def _get(
    url: str,
    *,
    timeout: float = LIST_TIMEOUT,
    budget: Optional[_SourceBudget] = None,
) -> Optional[requests.Response]:
    """GET with short timeout. Returns None on hard failure; updates budget."""
    if budget and budget.abandoned:
        return None
    try:
        return _SESSION.get(url, timeout=timeout)
    except (requests.RequestException, OSError) as exc:
        print(f"Warning: Info Yatirim GET failed for {url}: {exc}", file=sys.stderr)
        if budget:
            budget.record_fail(f"timeout_or_error:{type(exc).__name__}")
        return None


LANDING_PAGES = {
    "daily": "https://infoyatirim.com/arastirma/gunluk-bulten",
    "technical": "https://infoyatirim.com/arastirma/teknik-bulten",
}


def _slug_for_date(d: date) -> str:
    return f"{d.day:02d}{d.month:02d}{d.year}"


def _find_archive_link(
    landing_url: str,
    target_date: date,
    budget: _SourceBudget,
) -> Optional[str]:
    """Find the per-day archive link from the landing page pagination."""
    needle = f"bulten-{_slug_for_date(target_date)}"
    for page in range(1, 4):
        if budget.abandoned:
            return None
        url = f"{landing_url}?page={page}" if page > 1 else landing_url
        resp = _get(url, timeout=LIST_TIMEOUT, budget=budget)
        if resp is None:
            continue
        resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if needle in href:
                return href if href.startswith("http") else f"https://infoyatirim.com{href}"
    return None


def _find_bulletin_uuid(
    landing_url: str,
    target_date: date,
    budget: _SourceBudget,
) -> tuple[Optional[str], Optional[str]]:
    """
    Find the bulletin UUID and the archive page URL/label.
    Returns (uuid, archive_label_or_url).
    """
    if budget.abandoned:
        return None, None

    archive_url = _find_archive_link(landing_url, target_date, budget)
    archive_label = None
    if archive_url and not budget.abandoned:
        resp = _get(archive_url, timeout=LIST_TIMEOUT, budget=budget)
        if resp is not None:
            resp.encoding = "utf-8"
            archive_label = resp.text
            for m in re.finditer(r"/Content/Bulletin/([0-9a-fA-F-]{36})\.html", resp.text):
                return m.group(1), archive_label

    if budget.abandoned:
        return None, None

    # Fallback: latest from landing page
    resp = _get(landing_url, timeout=LIST_TIMEOUT, budget=budget)
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


def fetch_bulletin_content(
    uuid: str,
    archive_label: Optional[str] = None,
    budget: Optional[_SourceBudget] = None,
) -> str:
    url = f"https://cdn.infoyatirim.com/Content/Bulletin/{uuid}.html"
    resp = _get(url, timeout=BODY_TIMEOUT, budget=budget)
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
            r"(\d{1,2}\s+[a-zA-ZğüşöçıİĞÜŞÖÇ]+\s+\d{4})\s+Teknik Bülteni|"
            r"(\d{1,2}\s+[a-zA-ZğüşöçıİĞÜŞÖÇ]+\s+\d{4})\s+Günlük Bülteni",
            archive_label,
            re.I,
        )
        if m:
            label = m.group(0)
    text = f"{label}\n{body}" if label else body
    return "\n".join(line for line in text.splitlines() if line.strip())


def fetch_info_yatirim(target_date: date, cache_dir: Path) -> dict:
    cache_file = cache_dir / f"info_yatirim_{target_date.isoformat()}.json"
    if cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        if cached.get("daily", {}).get("content") and cached.get("technical", {}).get("content"):
            return cached

    daily_budget = _SourceBudget("daily")
    daily_uuid, daily_label = _find_bulletin_uuid(
        LANDING_PAGES["daily"], target_date, daily_budget
    )
    daily_content = ""
    if daily_uuid and not daily_budget.abandoned:
        daily_content = fetch_bulletin_content(daily_uuid, daily_label, daily_budget)

    # If daily already failed hard, skip technical — both are optional opinion
    # sources and burning another minute on the same dead host is wasteful.
    technical_uuid: Optional[str] = None
    technical_label: Optional[str] = None
    technical_content = ""
    technical_skip_reason = ""
    if daily_budget.abandoned or (not daily_uuid and daily_budget.failures >= MAX_SOURCE_FAILURES):
        technical_skip_reason = f"skipped_after_daily_fail:{daily_budget.reason or 'no_uuid'}"
        print(
            f"Warning: Info Yatirim technical {technical_skip_reason}",
            file=sys.stderr,
        )
    else:
        technical_budget = _SourceBudget("technical")
        technical_uuid, technical_label = _find_bulletin_uuid(
            LANDING_PAGES["technical"], target_date, technical_budget
        )
        if technical_uuid and not technical_budget.abandoned:
            technical_content = fetch_bulletin_content(
                technical_uuid, technical_label, technical_budget
            )

    result = {
        "ok": bool(daily_content) or bool(technical_content),
        "target_date": target_date.isoformat(),
        "daily": {
            "uuid": daily_uuid or "",
            "url": (
                f"https://cdn.infoyatirim.com/Content/Bulletin/{daily_uuid}.html"
                if daily_uuid
                else ""
            ),
            "content": daily_content,
            "status": "ok" if daily_content else "fail",
            "detail": "" if daily_content else (daily_budget.reason or "not_found"),
        },
        "technical": {
            "uuid": technical_uuid or "",
            "url": (
                f"https://cdn.infoyatirim.com/Content/Bulletin/{technical_uuid}.html"
                if technical_uuid
                else ""
            ),
            "content": technical_content,
            "status": "ok" if technical_content else "fail",
            "detail": (
                technical_skip_reason
                if technical_skip_reason
                else ("" if technical_content else "not_found")
            ),
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
