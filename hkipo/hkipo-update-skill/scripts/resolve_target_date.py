#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hong Kong (UTC+8) trading-day helpers + built-in HKEX public holidays.

Holidays are pre-computed for 2024-2027. For other years, rely on the weekly
weekend rule and add explicit entries via config.json `holidays`.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

HK_TZ = timezone(timedelta(hours=8))

# HKEX standard public holidays (closed days).
# Source: HKEX trading calendar. Extend here when a new year lands.
HKEX_HOLIDAYS = {
    # 2024
    "2024-01-01", "2024-02-13", "2024-02-14", "2024-02-15",  # 元旦/春节D3-5
    "2024-03-29", "2024-04-01", "2024-04-04", "2024-04-05",  # 耶稣受难/复活节星期一/清明
    "2024-05-01", "2024-05-15", "2024-05-19",                 # 劳动节/佛诞补假
    "2024-06-10",                                              # 端午补假
    "2024-07-01",                                              # 特区成立
    "2024-09-18",                                              # 中秋翌日
    "2024-10-01", "2024-10-11",                                # 国庆/重阳
    "2024-12-25", "2024-12-26",                                # 圣节/节礼日
    # 2025
    "2025-01-01",
    "2025-01-29", "2025-01-30", "2025-01-31",                  # 春节D1-D3
    "2025-04-04", "2025-04-18", "2025-04-21",                  # 清明/耶稣受难/复活节
    "2025-05-01", "2025-05-05",                                # 劳动节/佛诞
    "2025-05-31", "2025-06-30",                                # 端午/特区政府补假
    "2025-07-01",                                              # 特区成立
    "2025-10-01", "2025-10-07", "2025-10-29",                  # 国庆/重阳
    "2025-12-25", "2025-12-26",
    # 2026
    "2026-01-01",
    "2026-02-17", "2026-02-18", "2026-02-19",                  # 春节D1-D3
    "2026-04-03", "2026-04-06", "2026-04-07",                  # 清明/耶稣受难/复活节补
    "2026-05-01", "2026-05-25",                                # 劳动节/佛诞
    "2026-06-19",                                              # 端午
    "2026-07-01",                                              # 特区成立
    "2026-09-25",                                              # 中秋翌日
    "2026-10-01", "2026-10-19",                                # 国庆/重阳
    "2026-12-25", "2026-12-26",
    # 2027 (provisional — will refresh in 2027)
    "2027-01-01",
    "2027-02-06", "2027-02-08", "2027-02-09",                  # 春节
    "2027-03-26", "2027-03-29",                                # 耶稣受难/复活节
    "2027-04-05", "2027-04-09",                                # 清明/佛诞补
    "2027-05-01", "2027-05-21",                                # 劳动节/佛诞
    "2027-06-09",                                              # 端午
    "2027-07-01",                                              # 特区成立
    "2027-09-16",                                              # 中秋翌日
    "2027-10-01", "2027-10-08",                                # 国庆/重阳
    "2027-12-25", "2027-12-26",
}


def today_hk() -> date:
    return datetime.now(HK_TZ).date()


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def is_holiday(d: date, extra_holidays: Optional[List[str]] = None) -> bool:
    iso = d.isoformat()
    if iso in HKEX_HOLIDAYS:
        return True
    if extra_holidays:
        return iso in extra_holidays
    return False


def is_trading_day(d: date, extra_holidays: Optional[List[str]] = None) -> bool:
    return not is_weekend(d) and not is_holiday(d, extra_holidays)


def previous_trading_day(d: date, extra_holidays: Optional[List[str]] = None) -> date:
    """Largest trading day strictly before d."""
    cur = d
    while True:
        cur -= timedelta(days=1)
        if is_trading_day(cur, extra_holidays):
            return cur


def next_trading_day(d: date, extra_holidays: Optional[List[str]] = None) -> date:
    cur = d
    while True:
        cur += timedelta(days=1)
        if is_trading_day(cur, extra_holidays):
            return cur


def trading_day_minus(d: date, n: int, extra_holidays: Optional[List[str]] = None) -> date:
    """d minus n trading days (n=1 = previous_trading_day)."""
    cur = d
    for _ in range(max(0, n)):
        cur = previous_trading_day(cur, extra_holidays)
    return cur


def resolve_target_date(
    forced: Optional[str] = None,
    extra_holidays: Optional[List[str]] = None,
    allow_non_trading: bool = False,
) -> date:
    """Default: today if trading day, else previous trading day.

    Set allow_non_trading=True to force return today's date even on weekends/holidays
    (useful for cleanup_listed which runs Sundays).
    """
    if forced:
        return date.fromisoformat(forced)
    today = today_hk()
    if allow_non_trading:
        return today
    if not is_trading_day(today, extra_holidays):
        return previous_trading_day(today, extra_holidays)
    return today


def grey_date_for(listing_date: date, extra_holidays: Optional[List[str]] = None) -> Optional[date]:
    """暗盘 = listing_date − 1 trading day. Returns None if listing_date missing."""
    if not listing_date:
        return None
    return previous_trading_day(listing_date, extra_holidays)
