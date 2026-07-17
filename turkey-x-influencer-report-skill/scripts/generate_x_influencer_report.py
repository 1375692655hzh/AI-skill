#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main entry: fetch X influencers (TR yesterday 00:00→now via xAI), translate, write reports."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from build_curated_prompt import build_curated_prompt
from build_full_report import build_full_report
from fetch_tweets import fetch_and_cache, resolve_accounts_path
from llm_runner import generate_with_validation
from resolve_target_date import is_trading_day_open, resolve_target_date, today_tr
from runtime_utils import configure_stdio, resolve_paths
from translate_posts import translate_posts
from validate_output import validate_curated_report, validate_full_report


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def ensure_accounts_file(skill_dir: Path, accounts_path: Path) -> Path:
    if accounts_path.is_file():
        return accounts_path
    example = skill_dir / "accounts.example.yaml"
    if example.is_file() and accounts_path.name == "accounts.yaml":
        shutil.copy(example, accounts_path)
        print(f"Created {accounts_path} from accounts.example.yaml", file=sys.stderr)
        return accounts_path
    return accounts_path


def generate(
    config_path: Path,
    force_date: str | None = None,
    force_refresh: bool = False,
    no_translate: bool = False,
    no_curated: bool = False,
) -> tuple[Path | None, Path | None]:
    configure_stdio()
    config = load_config(config_path)
    skill_dir, workdir, output_dir, cache_dir, template_path = resolve_paths(
        config_path,
        config,
        default_cache=".cache/turkey-x-influencer-report",
        default_template="templates/curated_template.txt",
    )
    os.chdir(workdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    holidays = config.get("holidays", [])
    target_date = resolve_target_date(force_date, holidays)
    print(f"Today (TR): {today_tr()}")
    print(f"Target date: {target_date}")

    if not is_trading_day_open(target_date, holidays) and not force_date:
        print(f"Target date {target_date} is weekend/holiday. Skip.")
        return None, None
    if not is_trading_day_open(target_date, holidays) and force_date:
        print(f"Warning: forced date {target_date} is weekend/holiday; continuing.")

    try:
        accounts_path = resolve_accounts_path(skill_dir, config.get("accounts_path", "accounts.yaml"))
    except FileNotFoundError as exc:
        # Auto-create from example if missing
        configured = Path(config.get("accounts_path", "accounts.yaml"))
        if not configured.is_absolute():
            configured = skill_dir / configured
        ensure_accounts_file(skill_dir, configured)
        accounts_path = resolve_accounts_path(skill_dir, config.get("accounts_path", "accounts.yaml"))
        if not accounts_path.is_file():
            print(str(exc), file=sys.stderr)
            return None, None

    print(f"Accounts: {accounts_path}")
    fetch_cfg = config.get("fetch", {})
    try:
        bundle = fetch_and_cache(
            accounts_path,
            cache_dir,
            target_date.isoformat(),
            fetch_cfg,
            force_refresh=force_refresh,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return None, None
    posts = list(bundle.get("posts") or [])
    window_h = bundle.get("hours", "?")
    print(
        f"Posts in window (TR yesterday 00:00→now, ~{window_h}h): {len(posts)} "
        f"(raw={bundle.get('raw_count', 0)}, ok_accounts={bundle.get('ok_accounts', '?')}, "
        f"fail_accounts={bundle.get('fail_accounts', 0)})"
    )
    if bundle.get("provider_hits"):
        print(f"Provider hits: {bundle['provider_hits']}")
    if bundle.get("truncated_accounts"):
        print(f"Truncated accounts (page/limit cap): {bundle['truncated_accounts']}")
    if bundle.get("failures"):
        print(f"Fetch failures: {len(bundle['failures'])}")

    translate_cfg = config.get("translate", {})
    llm_cfg = config.get("llm", {})
    do_translate = bool(translate_cfg.get("enabled", True)) and not no_translate
    if do_translate and posts:
        posts = translate_posts(posts, llm_cfg, translate_cfg)
        # Persist translations into cache
        bundle["posts"] = posts
        cache_file = cache_dir / f"posts_{target_date.isoformat()}.json"
        cache_file.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    elif not do_translate:
        for p in posts:
            p.setdefault("translation", "")
            p.setdefault("quoted_translation", "")

    meta = {
        "hours": bundle.get("hours", ""),
        "window": bundle.get("window", "yesterday_start_to_now"),
        "window_label": f"TR 昨天 00:00 → 现在（约 {bundle.get('hours', '?')}h）",
        "since": bundle.get("since", ""),
        "until": bundle.get("until", ""),
        "accounts": bundle.get("accounts") or [],
        "failures": bundle.get("failures") or [],
        "truncated_accounts": bundle.get("truncated_accounts") or [],
    }
    full_text = build_full_report(target_date, posts, meta)
    full_check = validate_full_report(full_text)
    if not full_check["ok"]:
        print(f"Full report validation: {full_check['errors']}", file=sys.stderr)

    full_path = output_dir / f"{target_date.isoformat()}_x_influencer_full_zh.txt"
    full_path.write_text(full_text, encoding="utf-8")
    print(f"Full report: {full_path}")

    curated_path: Path | None = None
    curated_cfg = config.get("curated", {})
    do_curated = bool(curated_cfg.get("enabled", True)) and not no_curated
    if do_curated:
        if not template_path.is_file():
            print(f"Curated template missing: {template_path}", file=sys.stderr)
        elif not posts:
            curated_text = (
                f"【推特大V精选 — {target_date.isoformat()}】\n"
                "窗口内（TR 昨天 00:00→现在）无可用帖子，未生成精选分析。\n\n"
                "【精选热点】\n无\n\n【背景说明】\n无\n\n【投资分析】\n无\n\n【风险提示】\n无数据。\n"
            )
            curated_path = output_dir / f"{target_date.isoformat()}_x_influencer_curated_zh.txt"
            curated_path.write_text(curated_text, encoding="utf-8")
            print(f"Curated report (empty posts): {curated_path}")
        else:
            prompt = build_curated_prompt(
                template_path,
                target_date,
                posts,
                excerpt_chars=int(curated_cfg.get("excerpt_chars_per_post", 600)),
                max_posts=int(curated_cfg.get("max_posts_in_prompt", 80)),
            )
            prompt_file = cache_dir / f"curated_prompt_{target_date.isoformat()}.txt"
            prompt_file.write_text(prompt, encoding="utf-8")
            print(f"Curated prompt: {prompt_file}")

            curated_llm = {
                **llm_cfg,
                "temperature": curated_cfg.get("temperature", llm_cfg.get("temperature", 0.3)),
                "max_tokens": curated_cfg.get("max_tokens", llm_cfg.get("max_tokens", 8000)),
            }
            curated_text, result = generate_with_validation(
                prompt,
                curated_llm,
                validate_curated_report,
            )
            if not curated_text:
                print(f"Curated LLM failed: {result}", file=sys.stderr)
            else:
                if not result.get("ok"):
                    print(f"Curated validation warnings/errors: {result}", file=sys.stderr)
                curated_path = output_dir / f"{target_date.isoformat()}_x_influencer_curated_zh.txt"
                curated_path.write_text(curated_text.strip() + "\n", encoding="utf-8")
                print(f"Curated report: {curated_path}")

    return full_path, curated_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Turkey X influencer report (xAI x_search, TR yesterday 00:00→now)"
    )
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--force-date", default=None, help="YYYY-MM-DD")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore tweet cache")
    parser.add_argument("--no-translate", action="store_true")
    parser.add_argument("--no-curated", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_file():
        alt = Path(__file__).resolve().parent.parent / "config.json"
        if alt.is_file():
            config_path = alt
        else:
            print(f"Config not found: {args.config}", file=sys.stderr)
            sys.exit(1)

    full_path, curated_path = generate(
        config_path,
        force_date=args.force_date,
        force_refresh=args.force_refresh,
        no_translate=args.no_translate,
        no_curated=args.no_curated,
    )
    sys.exit(0 if full_path else 2)


if __name__ == "__main__":
    main()
