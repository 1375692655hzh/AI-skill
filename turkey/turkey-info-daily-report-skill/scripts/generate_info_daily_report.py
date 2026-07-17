#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main entry: generate Turkey Info daily bulletin Chinese report."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from build_prompt import build_prompt
from check_source_date import is_content_for_date
from fetch_info_daily import fetch_info_daily
from llm_runner import generate_with_validation
from resolve_target_date import resolve_target_date, today_tr, is_trading_day_open
from runtime_utils import configure_stdio, resolve_paths
from validate_output import validate


WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def generate(config_path: Path, force_date: str | None = None, no_llm: bool = False) -> Path | None:
    configure_stdio()
    config = load_config(config_path)
    skill_dir, workdir, output_dir, cache_dir, template_path = resolve_paths(
        config_path,
        config,
        default_template="templates/info_daily_report_template.txt",
        default_cache=".cache/turkey-info-daily-report",
    )
    os.chdir(workdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not template_path.is_file():
        print(f"Template not found: {template_path}", file=sys.stderr)
        return None

    holidays = config.get("holidays", [])
    target_date = resolve_target_date(force_date, holidays)
    source_cfg = config.get("sources", {}).get("info_daily", {})
    use_project_fetcher = source_cfg.get("use_project_fetcher", False)
    project_workdir = Path(source_cfg.get("project_path", workdir)) if use_project_fetcher else workdir

    if not is_trading_day_open(target_date, holidays):
        print(f"Target date {target_date} is a weekend or holiday. Skip.")
        return None

    print(f"Today (TR): {today_tr()}")
    print(f"Target date: {target_date}")

    bulletin = fetch_info_daily(
        target_date,
        cache_dir,
        workdir=project_workdir,
        use_project_fetcher=use_project_fetcher,
    )
    content = bulletin.get("content", "")
    if content and not is_content_for_date(target_date, content, "info_yatirim"):
        print(f"Warning: bulletin date mismatch, discarding cache for {target_date}")
        cache_file = cache_dir / f"info_daily_{target_date.isoformat()}.json"
        if cache_file.exists():
            cache_file.unlink()
        bulletin = fetch_info_daily(
            target_date,
            cache_dir,
            workdir=project_workdir,
            use_project_fetcher=use_project_fetcher,
        )
        content = bulletin.get("content", "")

    if not bulletin.get("ok") or not content:
        reason = bulletin.get("reason", "not_found")
        fallback = bulletin.get("fallback_url", "https://infoyatirim.com/arastirma/gunluk-bulten")
        print(f"Daily bulletin not available for {target_date} (reason={reason}).")
        print(f"Fallback URL: {fallback}")
        return None

    weekday_cn = WEEKDAYS_CN[target_date.weekday()]
    prompt = build_prompt(
        template_path=template_path,
        target_date=target_date.isoformat(),
        weekday_cn=weekday_cn,
        bulletin_text=content,
    )

    prompt_file = cache_dir / f"daily_prompt_{target_date.isoformat()}.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    print(f"Prompt saved to: {prompt_file}")

    if no_llm:
        return prompt_file

    llm_cfg = config["llm"]
    report_content, result = generate_with_validation(prompt, llm_cfg, validate)
    if report_content is None or not result.get("ok"):
        if report_content:
            raw_output = cache_dir / f"daily_raw_output_{target_date.isoformat()}.txt"
            raw_output.write_text(report_content, encoding="utf-8")
            print(f"Validation failed: {result.get('errors', [])}")
            print(f"Raw output saved to: {raw_output}")
        else:
            print(f"Generation failed: {result.get('errors', [])}")
        return None

    if result.get("warnings"):
        print(f"Validation warnings: {result['warnings']}")

    output_file = output_dir / f"{target_date.isoformat()}_info_daily_report_zh.txt"
    output_file.write_text(report_content, encoding="utf-8")
    print(f"Info daily report written to: {output_file}")
    return output_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Turkey Info daily bulletin report")
    parser.add_argument("--config", type=Path, required=True, help="Path to config.json")
    parser.add_argument("--force-date", type=str, default=None, help="Force target date (YYYY-MM-DD)")
    parser.add_argument("--no-llm", action="store_true", help="Only build prompt, do not call LLM")
    args = parser.parse_args()

    try:
        generate(args.config, force_date=args.force_date, no_llm=args.no_llm)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
