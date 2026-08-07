#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compute 7 event types from a company row and UPSERT them into the events table.

Event types and their dates (aligned with HKIPO project `ipo_calendar.py`):
  offer_open   — date = company.offer_open_date,            time = 09:00
  cash_close   — date = company.cash_close_date,            time = 12:00 (default noon)
  margin_close — date = cash_close − 1 *natural* day,       time = 13:30
                  (港股惯例：融资截止通常在现金截止前一自然日)
  refund       — date = company.refund_date
                  (fallback: listing − 2 trading days),    time = 17:00
  grey_open    — date = listing − 1 trading day,            time = 16:00
  grey_close   — date = listing − 1 trading day,            time = 18:15
  listing      — date = company.listing_date,               time = 09:00

Each event carries payload = full company snapshot at the time of insertion.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from lib import db
from resolve_target_date import grey_date_for, previous_trading_day, trading_day_minus


def _safe_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _payload_for(company: Dict[str, Any]) -> Dict[str, Any]:
    """Compact company snapshot for the event payload (avoids storing row internals)."""
    keys = (
        "stock_code", "name_zh", "name_en", "business", "status",
        "offer_price_min", "offer_price_max", "board_lot", "public_offer_units",
        "total_mkt_cap_e8", "free_float_e8",
        "offer_open_date", "margin_close_date", "cash_close_date",
        "refund_date", "grey_date", "listing_date",
        "prospectus_url",
    )
    return {k: company.get(k) for k in keys if company.get(k) is not None}


def compute_dates(
    company: Dict[str, Any],
    *,
    extra_holidays: Optional[List[str]] = None,
) -> Dict[str, Optional[date]]:
    """Resolve all 7 event dates from a company row.

    This is the single source of truth for date arithmetic — exported so tests
    and the calendar UI can reuse it.

    Per HKIPO project conventions:
      margin_close = cash_close − 1 *natural* day   (港股惯例，非交易日)
      grey_date    = listing − 1 trading day
      refund_date  = listing − 2 trading days (when not explicitly provided)
    """
    offer_open = _safe_date(company.get("offer_open_date"))
    cash_close = _safe_date(company.get("cash_close_date"))
    refund = _safe_date(company.get("refund_date"))
    listing = _safe_date(company.get("listing_date"))
    grey = _safe_date(company.get("grey_date"))

    # margin_close: natural day −1 (港股惯例); fall back to trading-day −1 only
    # if the resulting date falls on a non-trading day AND an explicit override
    # is provided. By default we trust the natural-day rule.
    margin_close = _safe_date(company.get("margin_close_date"))
    if not margin_close and cash_close:
        margin_close = cash_close - timedelta(days=1)

    # grey_date: listing − 1 trading day
    if not grey and listing:
        grey = grey_date_for(listing, extra_holidays)

    # refund_date: listing − 2 trading days when not provided
    if not refund and listing:
        refund = trading_day_minus(listing, 2, extra_holidays)

    return {
        "offer_open": offer_open,
        "cash_close": cash_close,
        "margin_close": margin_close,
        "refund": refund,
        "grey": grey,
        "listing": listing,
    }


def compute_and_upsert(
    conn,
    company: Dict[str, Any],
    *,
    extra_holidays: Optional[List[str]] = None,
    margin_offset_days: int = 1,  # kept for backwards compat; ignored
) -> int:
    """Insert all 7 events for this company; returns count of inserted/touched rows.

    `margin_offset_days` is retained for call-site compatibility but no longer
    used — margin_close is always cash_close − 1 natural day per HKIPO convention.
    """
    payload = _payload_for(company)
    code = company.get("stock_code")
    if not code:
        return 0

    # Clear any stale unfired events for this company before re-inserting.
    # This handles the case where dates change between runs (e.g. PDF parser
    # fills in real listing_date after HKEX announcement date was used as a
    # placeholder). Already-fired events are preserved for idempotency.
    db.delete_unfired_events(conn, code)

    dates = compute_dates(company, extra_holidays=extra_holidays)

    n = 0
    # offer_open
    if dates["offer_open"]:
        n += int(db.upsert_event(
            conn, code, "offer_open", dates["offer_open"].isoformat(),
            event_time="09:00", payload=payload,
        ))
    # cash_close (default noon)
    if dates["cash_close"]:
        n += int(db.upsert_event(
            conn, code, "cash_close", dates["cash_close"].isoformat(),
            event_time=company.get("cash_close_time") or "12:00", payload=payload,
        ))
    # margin_close
    if dates["margin_close"]:
        n += int(db.upsert_event(
            conn, code, "margin_close", dates["margin_close"].isoformat(),
            event_time="13:30", payload=payload,
        ))
    # refund
    if dates["refund"]:
        n += int(db.upsert_event(
            conn, code, "refund", dates["refund"].isoformat(),
            event_time="17:00", payload=payload,
        ))
    # grey_open / grey_close (same date, different reminder times)
    if dates["grey"]:
        grey_payload = dict(payload)
        grey_payload["grey_session"] = "16:15-18:30"
        n += int(db.upsert_event(
            conn, code, "grey_open", dates["grey"].isoformat(),
            event_time="16:00", payload=grey_payload,
        ))
        n += int(db.upsert_event(
            conn, code, "grey_close", dates["grey"].isoformat(),
            event_time="18:15", payload=grey_payload,
        ))
    # listing
    if dates["listing"]:
        n += int(db.upsert_event(
            conn, code, "listing", dates["listing"].isoformat(),
            event_time="09:00", payload=payload,
        ))
    return n
