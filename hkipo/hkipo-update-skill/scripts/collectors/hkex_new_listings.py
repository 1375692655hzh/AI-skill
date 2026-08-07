#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HKEX New Listings + Predefined Prospectus collector.

This is the **primary source for in-offer (招股) detection**, ported from the
HKIPO project's `hkex_new_listing_client.py` and `hkex_predefined_prospectus_client.py`.
It is more authoritative than Tiger JSON because it covers companies that have
already published a prospectus but whose subscription window has not yet opened.

Two HTML surfaces, unioned by stock_code:

1. New-Listing Information pages (Main Board + GEM)
   https://www2.hkexnews.hk/New-Listings/New-Listing-Information/Main-Board?sc_lang=zh-HK
   https://www2.hkexnews.hk/New-Listings/New-Listing-Information/GEM?sc_lang=zh-HK
   → announcement / prospectus / allotment URLs + listing_date (from listconews URL)

2. Predefined Prospectus search (招股文件, last 7 days)
   https://www1.hkexnews.hk/search/predefineddoc.xhtml?lang=zh&predefineddocuments=6
   → prospectus_url + release_date as listing_date fallback

Output rows are consumed by `normalize.normalize_hkex_new_listing`.
"""
from __future__ import annotations

import re
import traceback
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

MAIN_BOARD_URL = (
    "https://www2.hkexnews.hk/New-Listings/New-Listing-Information/Main-Board?sc_lang=zh-HK"
)
GEM_URL = (
    "https://www2.hkexnews.hk/New-Listings/New-Listing-Information/GEM?sc_lang=zh-HK"
)
PREDEFINED_PROSPECTUS_URL = (
    "https://www1.hkexnews.hk/search/predefineddoc.xhtml"
    "?lang=zh&predefineddocuments=6"
)
HKEXNEWS_BASE = "https://www1.hkexnews.hk"

_STOCK_CODE_RE = re.compile(r"^\d{1,5}$")
_DATE_IN_URL_RE = re.compile(r"/(\d{4})/(\d{4})/")
_RELEASE_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_HKEX_LABEL_RE = re.compile(
    r"^(?:股份简称|股份簡稱|股份代号|股份代號|发放时间|發放時間)[:：]\s*"
)

# Host/path signals used to classify download links (HKEX renders every download
# link as "下載" with no title, so position-based classification is unreliable).
_ALLOTMENT_HOST = "iporesults.hkex.com.hk"
_PROSPECTUS_PATH_HINTS = ("IPO", "PHIP")


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass
class NewListingEntry:
    """A company on the HKEX new-listing or predefined-prospectus page."""

    stock_code: str
    name_zh: str
    name_en: str = ""
    announcement_url: Optional[str] = None
    prospectus_url: Optional[str] = None
    allotment_url: Optional[str] = None
    listing_date: Optional[str] = None  # ISO YYYY-MM-DD
    source_surface: str = ""  # "new_listing" | "predefined"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["display_name"] = (self.name_zh or self.name_en or "").strip()
        return d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _headers() -> Dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def abs_hkex_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(HKEXNEWS_BASE, url)
    return url


def date_from_listconews_url(url: Optional[str]) -> Optional[str]:
    """Extract YYYY-MM-DD from HKEX listconews path (/sehk/2026/0623/...)."""
    if not url:
        return None
    m = _DATE_IN_URL_RE.search(url)
    if not m:
        return None
    yyyy, mmdd = m.group(1), m.group(2)
    if len(mmdd) != 4:
        return None
    return f"{yyyy}-{mmdd[:2]}-{mmdd[2:]}"


def normalize_stock_code(code: Optional[str]) -> str:
    """Strip non-digits and leading zeros (so '01396' → '1396')."""
    digits = re.sub(r"\D", "", (code or "").strip())
    if not digits:
        return ""
    return digits.lstrip("0") or "0"


def strip_hkex_cell_label(text: Optional[str]) -> str:
    """Remove HKEX mobile-table prefixes (e.g. 股份简称：xxx)."""
    s = (text or "").strip()
    if not s:
        return ""
    prev = None
    while s != prev:
        prev = s
        s = _HKEX_LABEL_RE.sub("", s).strip()
    return s


def _classify_link(href: str) -> Optional[str]:
    """Return 'allotment' | 'prospectus' | 'announcement' | None by URL host/path."""
    if not href:
        return None
    host = href.split("/")[2] if href.startswith("http") and href.count("/") >= 3 else ""
    if _ALLOTMENT_HOST in host:
        return "allotment"
    path_upper = href.upper()
    if "/IPO/" in path_upper or "/PHIP/" in path_upper:
        return "prospectus"
    if "hkexnews" in host:
        return "announcement"
    return None


def _cell_text_without_heading(td: Any) -> str:
    """Text from a table cell, excluding mobile-list-heading label spans."""
    parts: List[str] = []
    for child in td.children:
        name = getattr(child, "name", None)
        if name == "span":
            classes = child.get("class") or []
            if "mobile-list-heading" in classes:
                continue
        if isinstance(child, str):
            text = child.strip()
        else:
            text = child.get_text(strip=True)
        if text:
            parts.append(text)
    if parts:
        return "".join(parts).strip()
    return td.get_text(strip=True)


# ---------------------------------------------------------------------------
# New-Listing Information page (Main Board + GEM)
# ---------------------------------------------------------------------------


def parse_new_listing_row(tr: Any) -> Optional[NewListingEntry]:
    """Parse a table row from the new-listing page.

    Cell layout is FIXED by the page's table header (5 columns):
      [0] 股份代號     — stock code
      [1] 股份名稱     — company name
      [2] 新上市公告   — announcement URL
      [3] 招股章程     — prospectus URL
      [4] 股份配發結果 — allotment URL

    We use **column position as primary classification** (the header is stable)
    and fall back to host/path heuristics only when a cell contains multiple
    links or no header context is available.
    """
    cells = tr.find_all("td")
    if len(cells) < 3:
        return None

    stock_code = cells[0].get_text(strip=True)
    if not _STOCK_CODE_RE.match(stock_code):
        return None
    code = normalize_stock_code(stock_code)

    name_text = strip_hkex_cell_label(_cell_text_without_heading(cells[1]))
    if not name_text:
        return None

    # Column-position classification (primary, per page header).
    # Some legacy rows may have only 3 cells (no separate allotment column);
    # in that case cells[2] holds all links and we fall back to host/path.
    announcement_url: Optional[str] = None
    prospectus_url: Optional[str] = None
    allotment_url: Optional[str] = None

    if len(cells) >= 5:
        announcement_url = _first_link(cells[2])
        prospectus_url = _first_link(cells[3])
        allotment_url = _first_link(cells[4])
    elif len(cells) == 4:
        announcement_url = _first_link(cells[2])
        prospectus_url = _first_link(cells[3])
    else:
        # 3 cells — use host/path classification as fallback
        links: List[Tuple[str, Optional[str]]] = []
        for cell in cells[2:]:
            for a in cell.find_all("a"):
                href = abs_hkex_url(a.get("href"))
                if href:
                    links.append((href, _classify_link(href)))
        for href, kind in links:
            if kind == "allotment" and not allotment_url:
                allotment_url = href
            elif kind == "prospectus" and not prospectus_url:
                prospectus_url = href
            elif kind == "announcement" and not announcement_url:
                announcement_url = href
        unclassified = [h for h, k in links if k is None]
        for href in unclassified:
            if announcement_url is None:
                announcement_url = href
            elif prospectus_url is None:
                prospectus_url = href
            elif allotment_url is None:
                allotment_url = href

    listing_date = date_from_listconews_url(announcement_url or prospectus_url)

    return NewListingEntry(
        stock_code=code,
        name_zh=name_text,
        name_en=name_text,
        announcement_url=announcement_url,
        prospectus_url=prospectus_url,
        allotment_url=allotment_url,
        listing_date=listing_date,
        source_surface="new_listing",
    )


def _first_link(cell: Any) -> Optional[str]:
    """First href in a table cell (or None)."""
    a = cell.find("a", href=True)
    return abs_hkex_url(a.get("href")) if a else None


def fetch_new_listings(url: str, snapshot_dir: Optional[Path] = None) -> List[NewListingEntry]:
    try:
        resp = requests.get(url, headers=_headers(), timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"[hkex_new_listings] error fetching {url}: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return []

    text = resp.content.decode("utf-8", errors="replace")
    if snapshot_dir is not None:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        # Use a stable Windows-safe filename derived from the URL path, not the
        # query string (which contains '?' — illegal in Windows filenames).
        path_tail = url.rstrip("/").split("/")[-1].split("?")[0]
        fname = path_tail or "page"
        (snapshot_dir / f"new_listing_{fname}.html").write_text(text, encoding="utf-8")

    soup = BeautifulSoup(text, "html.parser")
    entries: List[NewListingEntry] = []
    seen: set = set()
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            entry = parse_new_listing_row(row)
            if not entry or entry.stock_code in seen:
                continue
            seen.add(entry.stock_code)
            entries.append(entry)
    return entries


def fetch_all_new_listings(snapshot_dir: Optional[Path] = None) -> List[NewListingEntry]:
    """Fetch new listings from both Main Board and GEM, deduped by stock_code."""
    main = fetch_new_listings(MAIN_BOARD_URL, snapshot_dir)
    gem = fetch_new_listings(GEM_URL, snapshot_dir)
    out: List[NewListingEntry] = []
    seen: set = set()
    for entry in main + gem:
        if entry.stock_code in seen:
            continue
        seen.add(entry.stock_code)
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Predefined Prospectus search (招股文件, last 7 days)
# ---------------------------------------------------------------------------


def parse_predefined_row(tr: Any) -> Optional[NewListingEntry]:
    cells = tr.find_all("td")
    if len(cells) < 4:
        return None

    code_text = strip_hkex_cell_label(_cell_text_without_heading(cells[1]))
    m = _STOCK_CODE_RE.search(code_text)
    if not m:
        return None
    stock_code = normalize_stock_code(m.group(0))

    name_text = strip_hkex_cell_label(_cell_text_without_heading(cells[2]))
    if not name_text:
        return None

    release_text = strip_hkex_cell_label(_cell_text_without_heading(cells[0]))
    listing_date = _parse_release_time(release_text)

    link = cells[3].find("a", href=True)
    prospectus_url = abs_hkex_url(link.get("href")) if link else None
    if not prospectus_url:
        return None

    if not listing_date:
        listing_date = date_from_listconews_url(prospectus_url)

    return NewListingEntry(
        stock_code=stock_code,
        name_zh=name_text,
        name_en=name_text,
        prospectus_url=prospectus_url,
        listing_date=listing_date,
        source_surface="predefined",
    )


def _parse_release_time(text: Optional[str]) -> Optional[str]:
    """'DD/MM/YYYY HH:MM' → 'YYYY-MM-DD'."""
    if not text:
        return None
    m = _RELEASE_DATE_RE.search(text)
    if not m:
        return None
    day, month, year = m.group(1), m.group(2), m.group(3)
    return f"{year}-{month}-{day}"


def fetch_predefined_prospectus(
    url: Optional[str] = None,
    snapshot_dir: Optional[Path] = None,
) -> List[NewListingEntry]:
    target = url or PREDEFINED_PROSPECTUS_URL
    try:
        resp = requests.get(target, headers=_headers(), timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"[hkex_new_listings] error fetching predefined prospectus: {exc}")
        return []

    text = resp.content.decode("utf-8", errors="replace")
    if snapshot_dir is not None:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / "predefined_prospectus.html").write_text(text, encoding="utf-8")

    soup = BeautifulSoup(text, "html.parser")
    entries: List[NewListingEntry] = []
    seen: set = set()
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            entry = parse_predefined_row(row)
            if not entry or entry.stock_code in seen:
                continue
            seen.add(entry.stock_code)
            entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# Merge — union of predefined + new_listing (predefined fills prospectus_url
# gaps when a company hasn't yet appeared on the new-listing info page)
# ---------------------------------------------------------------------------


def merge_entries(
    predefined: List[NewListingEntry],
    new_listing: List[NewListingEntry],
) -> List[NewListingEntry]:
    merged: Dict[str, NewListingEntry] = {}
    for entry in new_listing:
        merged[entry.stock_code] = entry
    for entry in predefined:
        existing = merged.get(entry.stock_code)
        if not existing:
            merged[entry.stock_code] = entry
            continue
        # Prefer new-listing announcement/listing date but inherit prospectus_url
        prospectus_url = existing.prospectus_url or entry.prospectus_url
        listing_date = existing.listing_date or entry.listing_date
        merged[entry.stock_code] = NewListingEntry(
            stock_code=existing.stock_code,
            name_zh=existing.name_zh or entry.name_zh,
            name_en=existing.name_en or entry.name_en,
            announcement_url=existing.announcement_url or entry.announcement_url,
            prospectus_url=prospectus_url,
            allotment_url=existing.allotment_url or entry.allotment_url,
            listing_date=listing_date,
            source_surface=existing.source_surface,
        )
    return list(merged.values())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def collect(
    cfg: Dict[str, Any],
    snapshot_dir: Path,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Called by run_update.py. Returns (rows, status)."""
    status: Dict[str, str] = {}
    if not cfg.get("enabled", True):
        status["hkex_new_listings"] = "disabled"
        return [], status

    main_url = cfg.get("main_board_url") or MAIN_BOARD_URL
    gem_url = cfg.get("gem_url") or GEM_URL
    predefined_url = cfg.get("predefined_url") or PREDEFINED_PROSPECTUS_URL

    failures: List[str] = []
    new_listings: List[NewListingEntry] = []

    try:
        nl_main = fetch_new_listings(main_url, snapshot_dir)
        new_listings.extend(nl_main)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"main_board:{type(exc).__name__}")
        traceback.print_exc()

    try:
        nl_gem = fetch_new_listings(gem_url, snapshot_dir)
        new_listings.extend(nl_gem)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"gem:{type(exc).__name__}")
        traceback.print_exc()

    try:
        predefined = fetch_predefined_prospectus(predefined_url, snapshot_dir)
    except Exception as exc:  # noqa: BLE001
        predefined = []
        failures.append(f"predefined:{type(exc).__name__}")

    merged = merge_entries(predefined, new_listings)
    rows = [e.to_dict() for e in merged]

    if failures and not rows:
        status["hkex_new_listings"] = f"degraded:{','.join(failures)}"
    elif failures:
        status["hkex_new_listings"] = f"partial:{len(rows)}/{','.join(failures)}"
    else:
        status["hkex_new_listings"] = f"ok:{len(rows)}"
    return rows, status
