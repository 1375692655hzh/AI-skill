#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve the target close-report date in Turkey time."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional


TR_TZ = timezone(timedelta(hours=3))  # UTC+3, no DST

# Fixed Turkish / BIST closed days (month, day). Religious movable holidays not included.
FIXED_HOLIDAY_MD = (
    (1, 1),  # Yılbaşı
    (4, 23),  # Ulusal Egemenlik ve Çocuk Bayramı
    (5, 1),  # Emek ve Dayanışma Günü
    (5, 19),  # Atatürk'ü Anma, Gençlik ve Spor Bayramı
    (7, 15),  # Demokrasi ve Millî Birlik Günü
    (8, 30),  # Zafer Bayramı
    (10, 29),  # Cumhuriyet Bayramı
)


def today_tr() -> date:
    return datetime.now(TR_TZ).date()


def fixed_tr_holidays(ref: Optional[date] = None) -> List[str]:
    """
    Auto-generate fixed holidays for the reference year.
    From June onward, also include the next calendar year.
    """
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
    """Fixed auto holidays + optional config extras."""
    return sorted(set(fixed_tr_holidays(ref)) | set(extra or []))


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # Saturday=5, Sunday=6


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
    """
    For close report: target date is the previous business day, unless today
    is already a business day and user wants that day (e.g., with force-date).
    `holidays` are optional extras; fixed TR holidays are always merged in.
    """
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
    print("holidays:", ", ".join(merge_holidays()))
