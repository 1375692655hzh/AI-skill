#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve the target briefing date in Turkey time (UTC+3)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional


TR_TZ = timezone(timedelta(hours=3))  # UTC+3, no DST

# Fixed Turkish / BIST closed days (month, day). Religious movable holidays not included.
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
    return d.weekday() >= 5


def is_holiday(d: date, holidays: Optional[List[str]] = None) -> bool:
    return d.isoformat() in (holidays or [])


def previous_publish_day(
    d: date,
    holidays: Optional[List[str]] = None,
    *,
    skip_weekend: bool = False,
) -> date:
    """Walk backward to a day that is not skipped."""
    holidays = holidays or []
    while True:
        d -= timedelta(days=1)
        if skip_weekend and is_weekend(d):
            continue
        if is_holiday(d, holidays):
            continue
        return d


def resolve_target_date(
    forced: Optional[str] = None,
    holidays: Optional[List[str]] = None,
    *,
    skip_weekend: bool = False,
    use_fixed_holidays: bool = True,
) -> date:
    """
    Default: today's date in Turkey time.

    AA Morning Briefing often publishes on weekends; only holidays are skipped
    by default. Set skip_weekend=True to walk back over Sat/Sun as well.
    When use_fixed_holidays=True, `holidays` are optional extras merged with
    auto-generated fixed TR holidays.
    """
    holidays = merge_holidays(holidays) if use_fixed_holidays else list(holidays or [])
    if forced:
        return date.fromisoformat(forced)

    today = today_tr()
    if is_holiday(today, holidays) or (skip_weekend and is_weekend(today)):
        return previous_publish_day(today, holidays, skip_weekend=skip_weekend)
    return today


def is_publish_day(
    d: date,
    holidays: Optional[List[str]] = None,
    *,
    skip_weekend: bool = False,
    use_fixed_holidays: bool = True,
) -> bool:
    holidays = merge_holidays(holidays) if use_fixed_holidays else list(holidays or [])
    if is_holiday(d, holidays):
        return False
    if skip_weekend and is_weekend(d):
        return False
    return True


if __name__ == "__main__":
    import sys

    forced = sys.argv[1] if len(sys.argv) > 1 else None
    print(resolve_target_date(forced).isoformat())
    print("holidays:", ", ".join(merge_holidays()))
