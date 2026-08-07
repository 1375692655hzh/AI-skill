#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reminder entry — called at each of 6 daily time points by external scheduler.

Lookup events firing today for the given slot type. If any unfired events match,
render the template, push once (or one per event if merge disabled), mark fired.
No events → silent exit 0 (silent_when_no_event config default true).

Slots:
  cash_close    (08:30)   → event_type cash_close
  offer_open    (09:00)   → event_type offer_open + listing
  margin_close  (13:30)   → event_type margin_close
  grey_open     (16:00)   → event_type grey_open
  refund        (17:00)   → event_type refund
  grey_close    (18:15)   → event_type grey_close
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from lib import db  # noqa: E402
from resolve_target_date import resolve_target_date, today_hk  # noqa: E402
from runtime_utils import configure_stdio, resolve_skill_paths  # noqa: E402
import push_webhook  # noqa: E402


SLOT_TO_EVENT_TYPES: Dict[str, List[str]] = {
    "cash_close": ["cash_close"],
    "offer_open": ["offer_open", "listing"],
    "margin_close": ["margin_close"],
    "grey_open": ["grey_open"],
    "refund": ["refund"],
    "grey_close": ["grey_close"],
}

SLOT_TO_TEMPLATE: Dict[str, str] = {
    "cash_close": "reminder_cash_close.txt",
    "offer_open": "reminder_offer_open.txt",   # also used for listing
    "margin_close": "reminder_margin_close.txt",
    "grey_open": "reminder_grey.txt",
    "refund": "reminder_refund.txt",
    "grey_close": "reminder_grey.txt",
}

SLOT_TITLES: Dict[str, str] = {
    "cash_close": "港股新股·现金截止提醒",
    "offer_open": "港股新股·今日招股 / 上市",
    "margin_close": "港股新股·融资截止提醒",
    "grey_open": "港股新股·暗盘开始提醒",
    "refund": "港股新股·资金解冻提醒",
    "grey_close": "港股新股·暗盘结束提醒",
}


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_template(name: str) -> str:
    path = HERE.parent / "templates" / name
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def render(template: str, event: dict) -> str:
    """Render a template by str.format with the event row (company fields + payload)."""
    fields = dict(event)
    # event_type comes from events table; merge payload if present
    payload = fields.get("payload") or {}
    for k, v in payload.items():
        fields.setdefault(k, v)
    # Grey template uses slot to switch open/close text
    fields.setdefault("slot", fields.get("event_type", ""))
    # slot_label: "开始" for grey_open, "结束" for grey_close
    et = fields.get("event_type") or fields.get("slot") or ""
    if et == "grey_open":
        fields.setdefault("slot_label", "开始")
    elif et == "grey_close":
        fields.setdefault("slot_label", "结束")
    else:
        fields.setdefault("slot_label", "")
    # Provide defaults for missing fields
    for k in (
        "name_zh", "name_en", "business", "stock_code",
        "offer_price_min", "offer_price_max", "board_lot", "public_offer_units",
        "total_mkt_cap_e8", "free_float_e8",
        "offer_open_date", "margin_close_date", "cash_close_date",
        "refund_date", "grey_date", "listing_date", "prospectus_url",
        "event_date", "event_time",
    ):
        if fields.get(k) is None:
            fields[k] = "—"
    # If listing slot, swap to listing template content
    if fields.get("event_type") == "listing":
        listing_tpl = load_template("reminder_listing.txt")
        if listing_tpl:
            template = listing_tpl
    try:
        return template.format(**fields).strip()
    except (KeyError, IndexError) as exc:
        # Fallback: just dump key fields
        return f"港股新股提醒 {fields.get('name_zh')}（{fields.get('stock_code')}）\n日期 {fields.get('event_date')} {fields.get('event_time')}\n(template missing key: {exc})"


def run(config_path: Path, slot: str) -> int:
    configure_stdio()
    if slot not in SLOT_TO_EVENT_TYPES:
        print(f"unknown slot: {slot}; valid: {list(SLOT_TO_EVENT_TYPES)}", file=sys.stderr)
        return 2

    config = load_config(config_path)
    skill_dir, workdir, data_dir, output_dir, db_path = resolve_skill_paths(config_path, config)

    holidays = config.get("holidays") or []
    today = resolve_target_date(extra_holidays=holidays)
    today_iso = today.isoformat()

    event_types = SLOT_TO_EVENT_TYPES[slot]
    print(f"== hkipo remind slot={slot} today={today_iso} types={event_types}")

    with db.connect(db_path) as conn:
        events = db.fetch_due_events(conn, today_iso, event_types)
        if not events:
            print("no due events; silent exit")
            return 0

        template = load_template(SLOT_TO_TEMPLATE[slot])
        push_cfg = config.get("push") or {}
        log_path = output_dir / today_iso / "pushed_notifications.log"

        # Build one rendered message per event; merge or push one-by-one
        messages: List[tuple] = []
        for ev in events:
            text = render(template, ev)
            messages.append((ev["stock_code"], ev["event_type"], text))

        if push_cfg.get("merge_multi_event", True) and len(messages) > 1:
            merged = "\n---\n".join(t for _, _, t in messages)
            title = f"{SLOT_TITLES[slot]} ({len(messages)})"
            res = push_webhook.push(merged, push_cfg, title=title, log_path=log_path)
            # Skip mark_fired in dry_run so the next non-dry run will actually send
            if res.ok and not res.dry_run:
                for code, et, _ in messages:
                    db.mark_fired(conn, code, et, today_iso)
        else:
            all_ok = True
            for code, et, text in messages:
                title = f"{SLOT_TITLES[slot]} — {code}"
                res = push_webhook.push(text, push_cfg, title=title, log_path=log_path)
                if res.ok and not res.dry_run:
                    db.mark_fired(conn, code, et, today_iso)
                elif not res.ok:
                    all_ok = False
            return 0 if all_ok else 1
    return 0


def main():
    ap = argparse.ArgumentParser(description="HK IPO reminder slot")
    ap.add_argument("--config", default="config.json")
    ap.add_argument(
        "--type",
        required=True,
        choices=list(SLOT_TO_EVENT_TYPES.keys()),
        help="reminder slot type",
    )
    args = ap.parse_args()
    cfg = Path(args.config)
    if not cfg.is_file():
        alt = HERE.parent / "config.json"
        if alt.is_file():
            cfg = alt
        else:
            print(f"config not found: {args.config}", file=sys.stderr)
            sys.exit(2)
    sys.exit(run(cfg, args.type))


if __name__ == "__main__":
    main()
