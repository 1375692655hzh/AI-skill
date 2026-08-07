#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite state store for HK IPO skill — single source of truth, avoids JSON sprawl.

Schema:
- companies: one row per (stock_code), UPSERT on refresh
- events: (stock_code, event_type, event_date) — fired_at NULL until reminder fires
- daily_diff: one row per refresh date — summary of new filings/hearings/offers/listings

All timestamps stored as ISO-8601 strings (YYYY-MM-DD or YYYY-MM-DD HH:MM).
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    stock_code TEXT PRIMARY KEY,
    name_zh TEXT,
    name_en TEXT,
    business TEXT,
    status TEXT,
    offer_price_min REAL,
    offer_price_max REAL,
    board_lot INTEGER,
    public_offer_units INTEGER,
    total_mkt_cap_e8 REAL,
    free_float_e8 REAL,
    offer_open_date TEXT,
    margin_close_date TEXT,
    cash_close_date TEXT,
    refund_date TEXT,
    grey_date TEXT,
    listing_date TEXT,
    prospectus_url TEXT,
    source TEXT,
    fetched_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);
CREATE INDEX IF NOT EXISTS idx_companies_listing ON companies(listing_date);

CREATE TABLE IF NOT EXISTS events (
    stock_code TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_date TEXT NOT NULL,
    event_time TEXT,
    payload_json TEXT,
    fired_at TEXT,
    created_at TEXT,
    PRIMARY KEY (stock_code, event_type, event_date)
);

CREATE INDEX IF NOT EXISTS idx_events_date_type ON events(event_date, event_type, fired_at);

CREATE TABLE IF NOT EXISTS daily_diff (
    diff_date TEXT PRIMARY KEY,
    new_filings_json TEXT,
    new_hearings_json TEXT,
    new_offers_json TEXT,
    new_listings_json TEXT,
    sources_status_json TEXT,
    created_at TEXT
);
"""


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def connect(db_path):
    """Yield a sqlite3 connection; create parent dir + schema on first use."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


COMPANY_FIELDS = (
    "stock_code", "name_zh", "name_en", "business", "status",
    "offer_price_min", "offer_price_max", "board_lot", "public_offer_units",
    "total_mkt_cap_e8", "free_float_e8",
    "offer_open_date", "margin_close_date", "cash_close_date",
    "refund_date", "grey_date", "listing_date",
    "prospectus_url", "source", "fetched_at",
)


def upsert_company(conn, company: Dict[str, Any]) -> None:
    """UPSERT one company row by stock_code; missing keys default to None."""
    row = {k: company.get(k) for k in COMPANY_FIELDS}
    if not row["stock_code"]:
        raise ValueError("company.stock_code is required")
    row["fetched_at"] = row.get("fetched_at") or _now_iso()
    cols = ", ".join(COMPANY_FIELDS)
    placeholders = ", ".join(["?"] * len(COMPANY_FIELDS))
    updates = ", ".join(
        f"{c}=excluded.{c}" for c in COMPANY_FIELDS if c != "stock_code"
    )
    sql = (
        f"INSERT INTO companies ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(stock_code) DO UPDATE SET {updates};"
    )
    conn.execute(sql, [row[c] for c in COMPANY_FIELDS])


def get_company(conn, stock_code: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM companies WHERE stock_code=?;", (stock_code,)
    ).fetchone()
    return dict(row) if row else None


def list_companies(conn, status: Optional[str] = None) -> List[Dict[str, Any]]:
    if status:
        rows = conn.execute(
            "SELECT * FROM companies WHERE status=? ORDER BY stock_code;", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM companies ORDER BY stock_code;").fetchall()
    return [dict(r) for r in rows]


def upsert_event(
    conn,
    stock_code: str,
    event_type: str,
    event_date: str,
    event_time: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> bool:
    """INSERT event; if it already exists with fired_at, do nothing (idempotent)."""
    payload_json = json.dumps(payload, ensure_ascii=False) if payload else None
    cur = conn.execute(
        """
        INSERT INTO events (stock_code, event_type, event_date, event_time, payload_json, fired_at, created_at)
        VALUES (?, ?, ?, ?, ?, NULL, ?)
        ON CONFLICT(stock_code, event_type, event_date) DO UPDATE SET
            event_time = COALESCE(excluded.event_time, events.event_time),
            payload_json = COALESCE(excluded.payload_json, events.payload_json);
        """,
        (stock_code, event_type, event_date, event_time, payload_json, _now_iso()),
    )
    return cur.rowcount > 0


def fetch_due_events(
    conn,
    today_iso: str,
    event_types: Iterable[str],
) -> List[Dict[str, Any]]:
    """Events firing today, not yet fired, joined with their company row."""
    placeholders = ", ".join(["?"] * len(list(event_types)))
    rows = conn.execute(
        f"""
        SELECT e.event_type, e.event_date, e.event_time, e.payload_json,
               c.* FROM events e
        JOIN companies c ON c.stock_code = e.stock_code
        WHERE e.event_date = ? AND e.event_type IN ({placeholders})
          AND e.fired_at IS NULL
        ORDER BY e.event_time, c.stock_code;
        """,
        (today_iso, *event_types),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("payload_json"):
            try:
                d["payload"] = json.loads(d["payload_json"])
            except (ValueError, TypeError):
                d["payload"] = None
        out.append(d)
    return out


def mark_fired(
    conn,
    stock_code: str,
    event_type: str,
    event_date: str,
) -> None:
    conn.execute(
        "UPDATE events SET fired_at=? WHERE stock_code=? AND event_type=? AND event_date=?;",
        (_now_iso(), stock_code, event_type, event_date),
    )


def delete_company_and_events(conn, stock_code: str) -> None:
    """Used by cleanup after archiving a listed company."""
    conn.execute("DELETE FROM events WHERE stock_code=?;", (stock_code,))
    conn.execute("DELETE FROM companies WHERE stock_code=?;", (stock_code,))


def delete_unfired_events(conn, stock_code: str) -> int:
    """Delete all events for a company that have NOT yet fired.

    Called by compute_events before re-inserting events so that changed dates
    (e.g. listing_date corrected from HKEX announcement date to PDF timetable)
    don't leave orphan event rows. Already-fired events are preserved so the
    reminder system stays idempotent.
    """
    cur = conn.execute(
        "DELETE FROM events WHERE stock_code=? AND fired_at IS NULL;",
        (stock_code,),
    )
    return cur.rowcount


def list_listed_before(conn, cutoff_iso: str) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM companies WHERE status='listed' AND listing_date < ?;",
        (cutoff_iso,),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_daily_diff(
    conn,
    diff_date: str,
    new_filings: List[Dict[str, Any]],
    new_hearings: List[Dict[str, Any]],
    new_offers: List[Dict[str, Any]],
    new_listings: List[Dict[str, Any]],
    sources_status: Dict[str, str],
) -> None:
    conn.execute(
        """
        INSERT INTO daily_diff (diff_date, new_filings_json, new_hearings_json,
                                new_offers_json, new_listings_json, sources_status_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(diff_date) DO UPDATE SET
            new_filings_json=excluded.new_filings_json,
            new_hearings_json=excluded.new_hearings_json,
            new_offers_json=excluded.new_offers_json,
            new_listings_json=excluded.new_listings_json,
            sources_status_json=excluded.sources_status_json,
            created_at=excluded.created_at;
        """,
        (
            diff_date,
            json.dumps(new_filings, ensure_ascii=False),
            json.dumps(new_hearings, ensure_ascii=False),
            json.dumps(new_offers, ensure_ascii=False),
            json.dumps(new_listings, ensure_ascii=False),
            json.dumps(sources_status, ensure_ascii=False),
            _now_iso(),
        ),
    )
