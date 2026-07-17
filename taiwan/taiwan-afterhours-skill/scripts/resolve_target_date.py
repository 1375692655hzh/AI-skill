#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Taiwan (UTC+8) trading-day helpers."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

TW_TZ = timezone(timedelta(hours=8))


def today_tw() -> date:
    return datetime.now(TW_TZ).date()


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
    """Default: today in Taiwan if weekday, else previous business day."""
    holidays = holidays or []
    if forced:
        return date.fromisoformat(forced)
    today = today_tw()
    if is_weekend(today) or is_holiday(today, holidays):
        return previous_business_day(today, holidays)
    return today
