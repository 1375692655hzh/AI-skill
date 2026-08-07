#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalize fields from HKEX / Tiger / AAStocks into the unified `companies` shape.

Each source emits a list of dicts with source-specific keys; this module maps them
to the columns in lib/db.SCHEMA (see lib/db.py COMPANY_FIELDS).

Date strings are normalized to ISO-8601 (YYYY-MM-DD). Money in 亿港元. Lot in 股.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable, List, Optional

HK_TZ = timezone(timedelta(hours=8))

# Canonical status values
STATUS_FILED = "filed"        # 新递表（Application Proof 已提交，未聆讯）
STATUS_HEARING = "hearing"    # 已过聆讯（PHIP 发布）
STATUS_IN_OFFER = "in_offer"  # 正在招股
STATUS_LISTED = "listed"      # 已上市
STATUS_LAPSED = "lapsed"      # 失效/撤回/被拒


def _to_iso_date(value: Any) -> Optional[str]:
    """Accept epoch-ms, 'YYYY-MM-DD', 'YYYY/MM/DD', 'YYYY年MM月DD日', or already-ISO."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            # epoch ms (Tiger) → HK date
            return datetime.fromtimestamp(int(value) / 1000, tz=HK_TZ).date().isoformat()
        except (ValueError, OSError):
            return None
    s = str(value).strip()
    if not s:
        return None
    # Try common formats
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    # Chinese date
    m = re.match(r"^(\d{4})\D+(\d{1,2})\D+(\d{1,2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date().isoformat()
        except ValueError:
            pass
    return None


def _to_iso_datetime(value: Any) -> Optional[str]:
    """Epoch-ms → ISO datetime string 'YYYY-MM-DD HH:MM'."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(int(value) / 1000, tz=HK_TZ).strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError):
            return None
    return str(value)


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = re.sub(r"[,，¥$港元HK$\s]", "", str(value))
    try:
        return float(s)
    except ValueError:
        return None


def _to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = re.sub(r"[,，股]", "", str(value))
    try:
        return int(float(s))
    except ValueError:
        return None


def normalize_tiger(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map Tiger skytigris JSON fields → companies schema."""
    code = str(item.get("symbol") or item.get("stockCode") or "").strip()
    if not code:
        return {}
    # Pad to 5 digits, suffix .HK convention handled by caller if needed
    code = code.zfill(5)

    status_raw = str(item.get("status") or item.get("ipoStatus") or "").upper()
    status = {
        "OPEN": STATUS_IN_OFFER,
        "LISTED": STATUS_LISTED,
        "PENDING": STATUS_HEARING,
        "FILED": STATUS_FILED,
    }.get(status_raw, STATUS_HEARING)

    return {
        "stock_code": code,
        "name_zh": item.get("nameZh") or item.get("nameCn") or item.get("name") or None,
        "name_en": item.get("nameEn") or item.get("nameUs") or None,
        "business": item.get("business") or item.get("description") or None,
        "status": status,
        "offer_price_min": _to_float(item.get("minPrice") or item.get("priceLow")),
        "offer_price_max": _to_float(item.get("maxPrice") or item.get("priceHigh")),
        "board_lot": _to_int(item.get("minQty") or item.get("boardLot")),
        "public_offer_units": _to_int(item.get("OfferingSize") or item.get("publicOfferSize")),
        "total_mkt_cap_e8": _to_float(item.get("marketCap") or item.get("totalMktCap")),
        "free_float_e8": _to_float(item.get("freeFloat") or item.get("circulatingMarketCap")),
        "offer_open_date": _to_iso_date(item.get("offerOpenDate") or item.get("startDate")),
        "margin_close_date": _to_iso_date(item.get("marginCloseDate")),
        "cash_close_date": _to_iso_date(item.get("closingDate") or item.get("cashCloseDate")),
        "refund_date": _to_iso_date(item.get("refundDate")),
        "grey_date": _to_iso_date(item.get("greyDate") or item.get("greyOpeningTime")),
        "listing_date": _to_iso_date(item.get("listDate") or item.get("listingDate")),
        "prospectus_url": item.get("prospectusUrl") or item.get("prospectusLink"),
        "source": "tiger",
    }


def normalize_hkex_appindex(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map HKEX appindex entry → companies schema.

    Recognized `state` tags (set by collectors/hkex_appindex.py):
      active_application_proof — filed, awaiting hearing (新递表)
      active_phip              — passed hearing (聆讯通过)
      listed                   — already listed
      returned                 — HKEX returned the application

    For active_application_proof / active_phip rows there is no stock_code yet;
    we use `hkex_id` as the synthetic primary key so the same applicant doesn't
    collide across days. Once listed, the row carries `stock_code` and that
    becomes the canonical key.
    """
    state = str(item.get("state") or "").lower()
    has_phip = bool(item.get("has_phip"))

    # Determine status (canonical values from lib/normalize.py)
    if state == "listed":
        status = STATUS_LISTED
    elif state == "returned":
        status = STATUS_LAPSED
    elif state == "active_phip" or has_phip:
        status = STATUS_HEARING
    elif state == "active_application_proof":
        status = STATUS_FILED
    else:
        # Fall back to legacy `state` token parsing for back-compat
        legacy_state = str(item.get("state") or item.get("status") or "").lower()
        if "phip" in legacy_state:
            status = STATUS_HEARING
        elif "application proof" in legacy_state or legacy_state in ("active", "filed"):
            status = STATUS_FILED
        elif "listed" in legacy_state:
            status = STATUS_LISTED
        elif legacy_state in ("lapsed", "withdrawn", "rejected", "returned", "inactive"):
            status = STATUS_LAPSED
        else:
            status = STATUS_FILED

    # Primary key: prefer real stock_code (post-listing); else use hkex_id as
    # synthetic key so un-listed applicants are still trackable.
    code = str(item.get("stock_code") or "").strip()
    name = item.get("name_zh") or item.get("name") or item.get("applicantName")
    hkex_id = str(item.get("hkex_id") or "").strip()
    if not code and hkex_id:
        code = f"AP{hkex_id}"  # synthetic code for pre-listing applicants

    return {
        "stock_code": code,
        "name_zh": name,
        "name_en": item.get("name_en"),
        "business": item.get("business"),
        "status": status,
        "prospectus_url": item.get("prospectus_url"),
        "source": "hkex_appindex",
        # Milestone dates (not in companies schema, used for diff/audit only).
        # If you want them persisted, add columns `ap_date` / `phip_date` to
        # lib/db.py and extend COMPANY_FIELDS.
        "_ap_date": item.get("ap_date"),
        "_phip_date": item.get("phip_date"),
        "_filing_date": item.get("filing_date"),
        "_hkex_id": hkex_id or None,
    }


def normalize_aastocks(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map AAStocks IPO table row → companies schema (mostly cross-check fields)."""
    code = str(item.get("stock_code") or item.get("code") or "").strip()
    return {
        "stock_code": code,
        "name_zh": item.get("name_zh") or item.get("name"),
        "business": item.get("business"),
        "status": (
            STATUS_IN_OFFER if "招股" in str(item.get("status") or "")
            else STATUS_FILED if "擬上市" in str(item.get("status") or "")
            else STATUS_LISTED if "已上市" in str(item.get("status") or "")
            else None
        ),
        "offer_price_min": _to_float(item.get("price_low")),
        "offer_price_max": _to_float(item.get("price_high")),
        "board_lot": _to_int(item.get("board_lot")),
        "listing_date": _to_iso_date(item.get("listing_date")),
        "grey_date": _to_iso_date(item.get("grey_date")),
        "source": "aastocks",
    }


def normalize_hkex_new_listing(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map HKEX New Listings / Predefined Prospectus entry → companies schema.

    This is the **primary in_offer (招股) trigger source**: a company here has
    either published a prospectus (predefined surface) or appeared on HKEX
    new-listing info page. Either way it has crossed the hearing stage and is
    in / about-to-start its public offer.

    `listing_date` from this source is actually the *announcement* date
    (extracted from the listconews URL). The genuine expected-listing date
    comes from the prospectus PDF timetable and is filled by
    collectors/hkex_prospectus_pdf.py later.
    """
    code = str(item.get("stock_code") or "").strip()
    if not code:
        return {}
    return {
        "stock_code": code,
        "name_zh": item.get("name_zh") or item.get("name_en"),
        "name_en": item.get("name_en"),
        "status": STATUS_IN_OFFER,
        "prospectus_url": item.get("prospectus_url"),
        "listing_date": _to_iso_date(item.get("listing_date")),
        "source": "hkex_new_listings",
        # announcement_url / allotment_url kept for downstream use (PDF parser,
        # allotment watcher) but not part of the companies schema.
        "_announcement_url": item.get("announcement_url"),
        "_allotment_url": item.get("allotment_url"),
    }


# ---------------------------------------------------------------------------
# Fuzzy name matching (ported from HKIPO project) — used for HKEX id drift
# correction when the same applicant re-applies under a new HKEX id.
# ---------------------------------------------------------------------------

_MIN_MATCH_SCORE = 0.82
_BRAND_FILLERS = re.compile(
    r"(?:股份|有限|公司|集团|控股|科技|技术|智能|国际|中国|投资|发展|实业|控股|管理)+"
)
_PARENS_RE = re.compile(r"[（(][^）)]*[）)]")  # strip parenthesised segments


def _normalize_name_key(text: Optional[str]) -> str:
    """Lowercase, strip whitespace/punctuation for name comparison."""
    if not text:
        return ""
    s = re.sub(
        r"[\s\u3000\-_/\\.,，。:：;；'\"()（）\[\]【】]+", "", str(text).lower()
    )
    return s


def brand_key(text: Optional[str]) -> str:
    """Strip common legal-form suffixes and parenthesised regions to expose brand core.

    Example: '拿森智能科技（浙江）股份有限公司' → '拿森'
    """
    if not text:
        return ""
    s = _normalize_name_key(text)
    s = _PARENS_RE.sub("", s)  # drop「（浙江）」
    s = _BRAND_FILLERS.sub("", s)
    return s


def _sequence_ratio(a: str, b: str) -> float:
    """Standard-library fuzzy ratio using difflib.SequenceMatcher (no deps)."""
    if not a or not b:
        return 0.0
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()


def _score_query(query: str, candidate: str) -> float:
    """Similarity score in [0, 1] combining substring, brand-key, and sequence ratio."""
    q = _normalize_name_key(query)
    c = _normalize_name_key(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    if q in c or c in q:
        return 0.95
    qb, cb = brand_key(query), brand_key(candidate)
    if qb and cb:
        if qb == cb and len(qb) >= 2:
            return 0.9
        if (qb in cb or cb in qb) and min(len(qb), len(cb)) >= 2:
            return 0.88
    return _sequence_ratio(q, c)


def score_name_similarity(a: Optional[str], b: Optional[str]) -> float:
    """Public alias for _score_query; returns max of (direct, reversed) scores."""
    return max(_score_query(a or "", b or ""), _score_query(b or "", a or ""))


def merge_companies(*sources: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Merge N iterables of company dicts by stock_code; later non-None wins.

    Priority (pass in this order, lowest → highest precedence):
      1. hkex_appindex   — baseline (递表/聆讯/已上市 from HKEX JSON)
      2. hkex_new_listings — in_offer trigger (招股主判定，HKEX HTML 两个页面)
      3. aastocks        — cross-check (字段补充)
      4. tiger_json      — 字段补充 (招股价/每手/市值/截止时间等结构化字段)
      5. hkex_pdf        — prospectus-timetable dates (override all date fields)

    Note: status is NOT simply "last wins". hkex_new_listings forces status to
    in_offer; hkex_appindex with active_phip forces status to hearing. To keep
    precedence predictable we let later sources override status only when the
    new status represents a *later* stage in the lifecycle.
    """
    # Lifecycle rank: filed < hearing < in_offer < listed; lapsed is terminal low
    _RANK = {
        STATUS_LAPSED: -1,
        STATUS_FILED: 0,
        STATUS_HEARING: 1,
        STATUS_IN_OFFER: 2,
        STATUS_LISTED: 3,
    }

    merged: Dict[str, Dict[str, Any]] = {}
    for src in sources:
        for company in src:
            if not company:
                continue
            code = company.get("stock_code")
            if not code:
                continue
            cur = merged.setdefault(code, {"stock_code": code})
            for k, v in company.items():
                if v is None:
                    continue
                if k == "status":
                    cur_rank = _RANK.get(cur.get("status") or "", -2)
                    new_rank = _RANK.get(v, -2)
                    # Only let the new status override if it is at least as
                    # advanced as the current one. This prevents Tiger `PENDING`
                    # from clobbering an hkex_new_listings `in_offer`.
                    if new_rank < cur_rank:
                        continue
                cur[k] = v
    return merged


def to_e8_hkd(value: Optional[float]) -> Optional[float]:
    """Convert HKD to 亿港元 (divide by 1e8). Pass-through if already None."""
    if value is None:
        return None
    try:
        return round(float(value) / 1e8, 2)
    except (TypeError, ValueError):
        return None
