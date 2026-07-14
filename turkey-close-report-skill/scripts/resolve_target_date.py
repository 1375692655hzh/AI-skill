#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve the target close-report date in Turkey time."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional


TR_TZ = timezone(timedelta(hours=3))  # UTC+3, no DST


def today_tr() -> date:
    return datetime.now(TR_TZ).date()


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # Saturday=5, Sunday=6


def is_holiday(d: date, holidays: Optional[List[str]] = None) -> bool:
    if holidays is None:
        holidays = []
    return d.isoformat() in holidays


def previous_business_day(d: date, holidays: Optional[List[str]] = None) -> date:
    if holidays is None:
        holidays = []
    while True:
        d -= timedelta(days=1)
        if not is_weekend(d) and not is_holiday(d, holidays):
            return d


def resolve_target_date(
    forced: Optional[str] = None,
    holidays: Optional[List[str]] = None,
) -> date:
    """
    For close report: target date is the previous business day, unless today
    is already a business day and user wants that day (e.g., with force-date).
    """
    if forced:
        return date.fromisoformat(forced)

    today = today_tr()

    if is_weekend(today) or is_holiday(today, holidays):
        # After weekend/holiday, report on the last business day
        return previous_business_day(today, holidays)
    else:
        # Today is a business day; close report is about today
        return today


def is_trading_day_open(d: date, holidays: Optional[List[str]] = None) -> bool:
    return not is_weekend(d) and not is_holiday(d, holidays or [])


if __name__ == "__main__":
    import sys

    holidays = []
    forced = sys.argv[1] if len(sys.argv) > 1 else None
    print(resolve_target_date(forced, holidays).isoformat())
