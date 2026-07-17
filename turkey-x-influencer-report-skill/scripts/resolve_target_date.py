#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve target trading date in Turkey time (UTC+3)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional


TR_TZ = timezone(timedelta(hours=3))

FIXED_HOLIDAY_MD = (
    (1, 1),
    (4, 23),
    (5, 1),
    (5, 19),
    (7, 15),
    (8, 30),
    (10, 29),
)


def today_tr() -> date:
    return datetime.now(TR_TZ).date()


def fixed_tr_holidays(ref: Optional[date] = None) -> List[str]:
    if ref is None:
        ref = today_tr()
    years = [ref.year]
    if ref.month >= 6:
        years.append(ref.year + 1)
    return [date(y, m, d).isoformat() for y in years for m, d in FIXED_HOLIDAY_MD]


def merge_holidays(
    extra: Optional[List[str]] = None,
    ref: Optional[date] = None,
) -> List[str]:
    return sorted(set(fixed_tr_holidays(ref)) | set(extra or []))


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def is_holiday(d: date, holidays: Optional[List[str]] = None) -> bool:
    return d.isoformat() in (holidays or [])


def previous_business_day(d: date, holidays: Optional[List[str]] = None) -> date:
    holidays = holidays or []
    while True:
        d -= timedelta(days=1)
        if not is_weekend(d) and not is_holiday(d, holidays):
            return d


def resolve_target_date(
    forced: Optional[str] = None,
    holidays: Optional[List[str]] = None,
) -> date:
    """Today in TR if trading day; else previous business day. Forced date as-is."""
    holidays = merge_holidays(holidays)
    if forced:
        return date.fromisoformat(forced)
    today = today_tr()
    if is_weekend(today) or is_holiday(today, holidays):
        return previous_business_day(today, holidays)
    return today


def is_trading_day_open(d: date, holidays: Optional[List[str]] = None) -> bool:
    holidays = merge_holidays(holidays)
    return not is_weekend(d) and not is_holiday(d, holidays)


if __name__ == "__main__":
    import sys

    forced = sys.argv[1] if len(sys.argv) > 1 else None
    print(resolve_target_date(forced).isoformat())
