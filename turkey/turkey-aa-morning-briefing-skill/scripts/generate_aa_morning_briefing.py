#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main entry: fetch AA Morning Briefing, optionally translate to Chinese, write output."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from call_llm import call_llm
from fetch_aa_morning_briefing import fetch_aa_morning_briefing
from resolve_target_date import is_publish_day, resolve_target_date, today_tr
from runtime_utils import configure_stdio, resolve_paths
from validate_output import validate_output


SEPARATOR = "=" * 72


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def _split_header_body(output_text: str) -> tuple[str, str]:
    """Keep metadata header in English; translate body after ==== separator."""
    text = output_text or ""
    if SEPARATOR in text:
        head, _, body = text.partition(SEPARATOR)
        return head.rstrip() + "\n" + SEPARATOR + "\n", body.lstrip("\n")
    # Fallback: first blank line after title block
    parts = text.split("\n\n", 1)
    if len(parts) == 2:
        return parts[0] + "\n\n", parts[1]
    return "", text


def _translate_to_chinese(output_text: str, llm_cfg: dict, translate_cfg: dict) -> str:
    header, body = _split_header_body(output_text)
    if not body.strip():
        return output_text

    prompt = (
        "请将下列 Anadolu Agency Morning Briefing 英文正文翻译为简体中文。\n"
        "要求：\n"
        "1. 保留原有章节标题结构（如 TOP STORIES / BUSINESS & ECONOMY / SPORTS / NEWS IN BRIEF），"
        "标题可保留英文或译为中文，全文风格统一。\n"
        "2. 金融术语、股票代码、人名、机构名、国家名优先保留英文原文或通用译名。\n"
        "3. 不要摘要、不要增删事实；完整翻译。\n"
        "4. 只输出译文正文，不要解释。\n\n"
        f"{body}"
    )
    translated = call_llm(
        prompt=prompt,
        provider=str(llm_cfg.get("provider", "minimax")),
        model=str(llm_cfg.get("model", "MiniMax-M3")),
        api_key_env=str(llm_cfg.get("api_key_env", "MINIMAX_API_KEY")),
        base_url=llm_cfg.get("base_url"),
        temperature=float(translate_cfg.get("temperature", llm_cfg.get("temperature", 0.3))),
        max_tokens=int(translate_cfg.get("max_tokens", llm_cfg.get("max_tokens", 12000))),
        system_message="You are a professional news translator. Translate English market news into clear Simplified Chinese.",
    ).strip()
    if not translated:
        return output_text
    return header + translated + ("\n" if not translated.endswith("\n") else "")


def generate(
    config_path: Path,
    force_date: str | None = None,
    force_url: str | None = None,
    force_refresh: bool = False,
    no_llm: bool = False,
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

    translate_cfg = config.get("translate") or {}
    do_translate = bool(translate_cfg.get("enabled", True)) and not no_llm
    if do_translate:
        try:
            print("Translating body to Chinese via LLM...")
            output_text = _translate_to_chinese(output_text, config.get("llm") or {}, translate_cfg)
        except Exception as exc:
            print(f"Translation failed, keeping English: {exc}", file=sys.stderr)

    out_name = config.get("output_filename", "{date}_aa_morning_briefing_zh.txt")
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
    parser.add_argument("--no-llm", action="store_true", help="Skip Chinese translation, keep English")
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
        no_llm=args.no_llm,
    )
    sys.exit(0 if path else 2)


if __name__ == "__main__":
    main()
