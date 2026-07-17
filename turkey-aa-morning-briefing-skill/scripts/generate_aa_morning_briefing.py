#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main entry: fetch AA Morning Briefing and write full-text output."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fetch_aa_morning_briefing import fetch_aa_morning_briefing
from resolve_target_date import is_publish_day, resolve_target_date, today_tr
from runtime_utils import configure_stdio, resolve_paths
from validate_output import validate_output


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def generate(
    config_path: Path,
    force_date: str | None = None,
    force_url: str | None = None,
    force_refresh: bool = False,
) -> Path | None:
    configure_stdio()
    config = load_config(config_path)
    _, workdir, output_dir, cache_dir = resolve_paths(
        config_path,
        config,
        default_cache=".cache/turkey-aa-morning-briefing",
    )
    os.chdir(workdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    holidays = config.get("holidays", [])
    # AA often publishes on weekends; default only skips configured holidays.
    skip_weekend = bool(config.get("skip_weekend", False))
    skip_holidays = bool(config.get("skip_holidays", True))
    # Back-compat with older key
    if "skip_weekend_holiday" in config and config.get("skip_weekend_holiday"):
        skip_weekend = True
        skip_holidays = True

    cfg_date = config.get("target_date", "auto")
    resolve_kwargs = {
        "holidays": holidays,
        "skip_weekend": skip_weekend,
        "use_fixed_holidays": skip_holidays,
    }
    if force_date:
        target_date = resolve_target_date(force_date, **resolve_kwargs)
    elif cfg_date and cfg_date != "auto":
        target_date = resolve_target_date(str(cfg_date), **resolve_kwargs)
    else:
        target_date = resolve_target_date(None, **resolve_kwargs)

    print(f"Today (TR): {today_tr()}")
    print(f"Target date: {target_date}")

    if not force_date and not is_publish_day(
        target_date,
        holidays,
        skip_weekend=skip_weekend,
        use_fixed_holidays=skip_holidays,
    ):
        print(f"Target date {target_date} is skipped (weekend/holiday policy). Skip.")
        return None

    force_url = force_url or (config.get("sources", {}).get("aa_morning_briefing", {}) or {}).get("force_url") or None
    bundle = fetch_aa_morning_briefing(
        target_date,
        cache_dir,
        force_url=force_url or None,
        force_refresh=force_refresh,
    )

    if not bundle.get("ok"):
        print(
            f"Fetch failed: {bundle.get('reason')}. "
            f"Try search: {bundle.get('search_url', 'https://www.aa.com.tr/en/search?s=Morning+Briefing')}"
        )
        return None

    output_text = bundle.get("output_text") or ""
    ok, errors = validate_output(output_text)
    if not ok:
        print("Validation warnings/errors:")
        for e in errors:
            print(f"  - {e}")
        # Still write file; NEWS IN BRIEF position is hard requirement
        if any("NEWS IN BRIEF" in e and "bottom" in e for e in errors):
            print("Aborting: NEWS IN BRIEF must be at the bottom.")
            return None

    out_name = config.get("output_filename", "{date}_aa_morning_briefing.txt")
    out_file = output_dir / out_name.format(date=target_date.isoformat())
    out_file.write_text(output_text, encoding="utf-8")

    pub = bundle.get("published") or {}
    print(f"URL: {bundle.get('url')}")
    print(f"Discover via: {bundle.get('discover_source')}")
    print(f"Published (TR): {pub.get('tr', '')}")
    print(f"Published (Beijing): {pub.get('beijing', '')}")
    print(f"Page update: {bundle.get('page_update', '')}")
    print(f"Output: {out_file}")
    return out_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Anadolu Agency Morning Briefing")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--force-date", default=None, help="YYYY-MM-DD")
    parser.add_argument("--force-url", default=None, help="Override article URL")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cache")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_file():
        # Allow running from repo root
        alt = Path(__file__).resolve().parent.parent / "config.json"
        if alt.is_file():
            config_path = alt
        else:
            print(f"Config not found: {args.config}", file=sys.stderr)
            sys.exit(1)

    path = generate(
        config_path,
        force_date=args.force_date,
        force_url=args.force_url,
        force_refresh=args.force_refresh,
    )
    sys.exit(0 if path else 2)


if __name__ == "__main__":
    main()
