#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve today's date and the most recent completed trading day in Turkey."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Optional

TR_TZ = timezone(timedelta(hours=3))


def now_tr() -> datetime:
    return datetime.now(TR_TZ)


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # Saturday=5, Sunday=6


def load_holidays(holidays: Optional[list[str]]) -> set[date]:
    if not holidays:
        return set()
    result = set()
    for h in holidays:
        try:
            result.add(date.fromisoformat(h))
        except ValueError:
            continue
    return result


def previous_trading_day(start: date, holidays: set[date]) -> date:
    """Move backward until a non-weekend, non-holiday date is found."""
    d = start - timedelta(days=1)
    while is_weekend(d) or d in holidays:
        d -= timedelta(days=1)
    return d


def resolve_dates(
    forced_target: Optional[str] = None,
    holidays: Optional[list[str]] = None,
    now: Optional[datetime] = None,
) -> dict:
    """
    today_date: current Turkish trading day.
    target_date: most recent completed trading day for closing data.
    """
    if now is None:
        now = now_tr()

    holiday_set = load_holidays(holidays)

    if forced_target:
        target = date.fromisoformat(forced_target)
        today = target  # For forced mode, assume today is the next trading day
        # If target is weekend/holiday, adjust
        if is_weekend(target) or target in holiday_set:
            target = previous_trading_day(target + timedelta(days=1), holiday_set)
        return {
            "today_date": today.isoformat(),
            "target_date": target.isoformat(),
            "now_tr": now.isoformat(),
            "forced": True,
        }

    today = now.date()

    # If today is a holiday or weekend, treat as a non-trading day request.
    if is_weekend(today) or today in holiday_set:
        target = previous_trading_day(today, holiday_set)
        return {
            "today_date": today.isoformat(),
            "target_date": target.isoformat(),
            "now_tr": now.isoformat(),
            "forced": False,
            "holiday": True,
        }

    # If before market open (TR 10:00), the most recent completed trading day is yesterday.
    if now.time() < time(10, 0):
        target = previous_trading_day(today, holiday_set)
    else:
        # Market is open or has closed. For a morning briefing, we still use the previous close.
        target = previous_trading_day(today, holiday_set)

    return {
        "today_date": today.isoformat(),
        "target_date": target.isoformat(),
        "now_tr": now.isoformat(),
        "forced": False,
        "holiday": False,
    }


if __name__ == "__main__":
    import json, sys

    # Optional CLI: --force 2026-07-10
    force = None
    if "--force" in sys.argv:
        idx = sys.argv.index("--force")
        force = sys.argv[idx + 1]
    print(json.dumps(resolve_dates(forced_target=force), ensure_ascii=False, indent=2))
