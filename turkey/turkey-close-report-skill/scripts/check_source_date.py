#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helpers to verify fetched content matches the intended target date."""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional

from bs4 import BeautifulSoup


def _normalize_turkish(text: str) -> str:
    return (
        text.replace("ı", "i")
        .replace("I", "i")
        .replace("İ", "i")
        .replace("ş", "s")
        .replace("Ş", "s")
        .replace("ç", "c")
        .replace("Ç", "c")
        .replace("ğ", "g")
        .replace("Ğ", "g")
        .replace("ü", "u")
        .replace("Ü", "u")
        .replace("ö", "o")
        .replace("Ö", "o")
    )


def parse_turkish_date(text: str) -> Optional[date]:
    """Extract dd MMMM yyyy or dd/MM/yyyy from Turkish text."""
    months_tr = {
        "ocak": 1, "subat": 2, "mart": 3, "nisan": 4, "mayis": 5, "haziran": 6,
        "temmuz": 7, "agustos": 8, "eylul": 9, "ekim": 10, "kasim": 11, "aralik": 12,
    }
    norm = _normalize_turkish(text.lower())
    m = re.search(r"(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})", norm)
    if m:
        d, mon, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        month = months_tr.get(mon)
        if month:
            return date(y, month, d)
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", text)
    if m:
        d, mon, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mon, d)
        except ValueError:
            pass
    return None


def bloomberght_date(text: str) -> Optional[date]:
    """Best-effort date extraction for BloombergHT article text."""
    # Article body usually contains "13 Temmuz 2026 ..." near the top
    parsed = parse_turkish_date(text)
    if parsed:
        return parsed
    # Look for explicit dd/MM/yyyy or dd-MM-yyyy
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", text)
    if m:
        d, mon, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mon, d)
        except ValueError:
            pass
    return None


def paraborsa_date(title: str, content: str) -> Optional[date]:
    """Extract date from Paraborsa title or URL-like content."""
    # Title contains "(13.07.2026)" or "– 13.07.2026"
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", title)
    if m:
        d, mon, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mon, d)
        except ValueError:
            pass
    return parse_turkish_date(content)


def info_yatirim_date(content: str) -> Optional[date]:
    """Extract the most likely bulletin date from Info Yatırım content."""
    # The bulletin often says "13 Temmuz 2026" or references "son işlem günü"
    parsed = parse_turkish_date(content)
    if parsed:
        return parsed
    # Look for "13 Temmuz 2026" in the title/breadcrumb text (archive page often contains this)
    m = re.search(r"(Teknik Bülten|Günlük Bülten)\s*,?\s*(\d{1,2})\s+([a-zA-ZğüşöçıİĞÜŞÖÇ]+)\s+(\d{4})", content, re.I)
    if m:
        months_tr = {
            "ocak": 1, "subat": 2, "mart": 3, "nisan": 4, "mayis": 5, "haziran": 6,
            "temmuz": 7, "agustos": 8, "eylul": 9, "ekim": 10, "kasim": 11, "aralik": 12,
        }
        mon = _normalize_turkish(m.group(3).lower())
        month = months_tr.get(mon)
        if month:
            return date(int(m.group(4)), month, int(m.group(2)))
    return None


def is_content_for_date(target_date: date, content: str, source: str, tolerance_days: int = 1) -> bool:
    """
    Returns True if the extracted date from content matches target_date.

    For Info Yatırım, the bulletins are published pre-market and discuss the
    previous close plus today's outlook; allow up to `tolerance_days` slack.
    """
    if not content:
        return False
    if source == "bloomberght":
        parsed = bloomberght_date(content)
    elif source == "paraborsa":
        parsed = paraborsa_date("", content)
    elif source == "info_yatirim":
        parsed = info_yatirim_date(content)
    else:
        parsed = parse_turkish_date(content)

    if parsed is None:
        return False
    if parsed == target_date:
        return True
    if source == "info_yatirim" and abs((parsed - target_date).days) <= tolerance_days:
        return True
    return False
