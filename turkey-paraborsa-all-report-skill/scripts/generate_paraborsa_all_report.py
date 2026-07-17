#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main entry: fetch all Paraborsa commentaries and build synthesis report."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from build_concat import build_concat_section
from build_summary_prompt import build_prompt
from fetch_all_paraborsa import fetch_all_paraborsa
from llm_runner import generate_with_validation
from resolve_target_date import is_trading_day_open, resolve_target_date, today_tr
from runtime_utils import configure_stdio, resolve_paths
from validate_output import validate_report, validate_summary


WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def assemble_report(summary_text: str, concat_text: str) -> str:
    summary = summary_text.strip()
    if not summary.startswith("【综合总结"):
        summary = "【综合总结】\n" + summary
    concat = concat_text.strip()
    if not concat.startswith("【拼接内容"):
        concat = "【拼接内容】\n" + concat
    return f"{summary}\n\n{concat}\n"


def generate(
    config_path: Path,
    force_date: str | None = None,
    no_llm: bool = False,
    force_refresh: bool = False,
) -> Path | None:
    configure_stdio()
    config = load_config(config_path)
    _, workdir, output_dir, cache_dir, template_path = resolve_paths(
        config_path,
        config,
        default_template="templates/summary_template.txt",
        default_cache=".cache/turkey-paraborsa-all-report",
    )
    os.chdir(workdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not template_path.is_file():
        print(f"Template not found: {template_path}", file=sys.stderr)
        return None

    holidays = config.get("holidays", [])
    target_date = resolve_target_date(force_date, holidays)
    if not is_trading_day_open(target_date, holidays):
        print(f"Target date {target_date} is weekend/holiday. Skip.")
        return None

    fetch_cfg = config.get("fetch", {})
    print(f"Today (TR): {today_tr()}")
    print(f"Target date: {target_date}")

    bundle = fetch_all_paraborsa(
        target_date,
        cache_dir,
        allowed_prefixes=fetch_cfg.get("article_types"),
        include_period_ranges=fetch_cfg.get("include_period_ranges", True),
        delay_seconds=float(fetch_cfg.get("delay_seconds", 1.2)),
        retry_on_429=int(fetch_cfg.get("retry_on_429", 3)),
        force_refresh=force_refresh,
    )
    articles = bundle.get("articles", [])
    print(
        f"Discovered {bundle.get('discovered_count', 0)} articles; "
        f"fetched {bundle.get('fetched_ok_count', 0)} OK"
    )
    if not bundle.get("ok"):
        print(f"No article bodies fetched. Fallback: {bundle.get('fallback_url')}")
        return None

    concat_text = build_concat_section(target_date, articles)
    concat_file = output_dir / f"{target_date.isoformat()}_paraborsa_concat.txt"
    concat_file.write_text(concat_text, encoding="utf-8")
    print(f"Concat section written to: {concat_file}")

    weekday_cn = WEEKDAYS_CN[target_date.weekday()]
    summary_cfg = config.get("summary", {})
    prompt = build_prompt(
        template_path,
        target_date,
        weekday_cn,
        articles,
        excerpt_chars=int(summary_cfg.get("excerpt_chars_per_article", 5000)),
    )
    prompt_file = cache_dir / f"summary_prompt_{target_date.isoformat()}.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    print(f"Summary prompt saved to: {prompt_file}")

    if no_llm:
        preview = assemble_report("（未调用 LLM，仅生成拼接内容）", concat_text)
        preview_file = output_dir / f"{target_date.isoformat()}_paraborsa_all_report_preview.txt"
        preview_file.write_text(preview, encoding="utf-8")
        return preview_file

    llm_cfg = {
        **config["llm"],
        "max_tokens": summary_cfg.get("max_tokens", config["llm"].get("max_tokens", 12000)),
        "temperature": summary_cfg.get("temperature", config["llm"].get("temperature", 0.3)),
    }
    summary_text, result = generate_with_validation(prompt, llm_cfg, validate_summary)
    if summary_text is None or not result.get("ok"):
        if summary_text:
            raw = cache_dir / f"summary_raw_{target_date.isoformat()}.txt"
            raw.write_text(summary_text, encoding="utf-8")
            print(f"Summary validation failed: {result.get('errors')}")
            print(f"Raw summary saved to: {raw}")
        else:
            print(f"Summary generation failed: {result.get('errors')}")
        return None

    report = assemble_report(summary_text, concat_text)
    validation = validate_report(report, min_articles=max(1, bundle.get("fetched_ok_count", 1) // 2))
    if validation.get("warnings"):
        print(f"Report warnings: {validation['warnings']}")

    output_file = output_dir / f"{target_date.isoformat()}_paraborsa_all_report_zh.txt"
    output_file.write_text(report, encoding="utf-8")
    print(f"Full report written to: {output_file}")
    return output_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Paraborsa all-broker synthesis report")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--force-date", type=str, default=None)
    parser.add_argument("--no-llm", action="store_true", help="Only fetch + concat, skip summary LLM")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore fetch cache")
    args = parser.parse_args()
    try:
        generate(args.config, force_date=args.force_date, no_llm=args.no_llm, force_refresh=args.force_refresh)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
