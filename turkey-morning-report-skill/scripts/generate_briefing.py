#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main orchestration: generate the Turkish morning briefing."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

# Add skill scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from build_prompt import build_prompt
from call_llm import call_llm
from fetch_bloomberght_closing import fetch_closing_review
from fetch_news import fetch_news
from resolve_target_date import resolve_dates
from runtime_utils import configure_stdio, resolve_paths
from validate_output import validate


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="Generate Turkey morning briefing.")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--force-date", help="Force target date (YYYY-MM-DD) for testing")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM call, only build prompt")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config = load_config(config_path)

    skill_dir, workdir, output_dir, cache_dir, template_path = resolve_paths(
        config_path,
        config,
        default_template="templates/morning_briefing_template.txt",
        default_cache=".cache/turkey-morning-report",
    )
    os.chdir(workdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not template_path.is_file():
        print(f"Template not found: {template_path}", file=sys.stderr)
        return 1

    # 1. Resolve dates
    dates = resolve_dates(
        forced_target=args.force_date,
        holidays=config.get("holidays"),
    )
    today_date = dates["today_date"]
    target_date = dates["target_date"]

    print(f"Today (TR): {today_date}", file=sys.stderr)
    print(f"Target date: {target_date}", file=sys.stderr)

    if dates.get("holiday"):
        print(f"Today {today_date} is a holiday or weekend. No briefing generated.", file=sys.stderr)
        return 0

    output_file = output_dir / f"{today_date}_daily_briefing_zh.txt"
    if output_file.exists() and not args.force_date:
        print(f"Output already exists: {output_file}", file=sys.stderr)
        # Continue anyway to allow re-generation

    closing_cfg = config.get("sources", {}).get("bloomberght_closing", {})

    # 2. Fetch closing review
    closing = fetch_closing_review(
        target_date=date.fromisoformat(target_date),
        cache_dir=cache_dir,
        workdir=workdir,
        closing_cfg=closing_cfg,
        rss_url=closing_cfg.get("rss_url", "https://www.bloomberght.com/rss"),
    )
    if not closing.get("ok"):
        print(f"Warning: closing review fetch failed: {closing.get('error')}", file=sys.stderr)
    closing_text = closing.get("text") or closing.get("error") or "无收盘数据"

    # 3. Fetch news
    news_cfg = config.get("sources", {}).get("news", {})
    news = fetch_news(
        target_date=date.fromisoformat(target_date),
        cache_dir=cache_dir,
        news_cfg=news_cfg,
        workdir=workdir,
        closing_cfg=closing_cfg,
    )

    # Build news text from multiple sources
    news_parts = []

    # 3a. BloombergHT breaking news (SON DAKİKA)
    bht = news.get("bloomberght", {})
    breaking = bht.get("breaking_news", [])
    featured = bht.get("featured_news", [])

    if breaking:
        news_parts.append("【盘中突发】")
        for item in breaking:
            news_parts.append(item.get("title", ""))

    if featured:
        news_parts.append("\n【重点资讯】")
        for item in featured:
            news_parts.append(item.get("title", ""))

    # 3b. Web search results (if BloombergHT news is insufficient)
    if not breaking and not featured:
        if news["web_search"]["results"]:
            for item in news["web_search"]["results"]:
                news_parts.append(f"{item.get('title', '')}: {item.get('snippet', '')}")
        if news["x_search"]["results"]:
            for item in news["x_search"]["results"]:
                news_parts.append(f"{item.get('title', '')}: {item.get('snippet', '')}")

    news_text = "\n".join(news_parts) if news_parts else "（无补充新闻数据）"

    # 4. Build prompt
    prompt = build_prompt(
        template_path=template_path,
        today_date=today_date,
        target_date=target_date,
        closing_text=closing_text,
        news_text=news_text,
    )

    if args.no_llm:
        prompt_file = cache_dir / f"prompt_{today_date}.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        print(f"Prompt saved to: {prompt_file}")
        return 0

    # 5. Call LLM
    llm_cfg = config["llm"]
    try:
        output = call_llm(
            prompt=prompt,
            provider=llm_cfg.get("provider", "openai"),
            model=llm_cfg.get("model", "gpt-4o"),
            api_key_env=llm_cfg.get("api_key_env", "OPENAI_API_KEY"),
            base_url=llm_cfg.get("base_url"),
            temperature=llm_cfg.get("temperature", 0.4),
            max_tokens=llm_cfg.get("max_tokens", 2500),
        )
    except Exception as e:
        print(f"LLM call failed: {e}", file=sys.stderr)
        return 1

    validation = validate(output)
    if not validation["ok"] and validation.get("attribution_hits"):
        fix_prompt = (
            prompt
            + "\n\n【重要修订】你上一版草稿仍出现了来源署名（如券商、平台、研究机构名称）。"
            "请完全重写：正文不得出现任何机构/平台/网站/报告名称，"
            "也不得使用「某某指出/认为/提示/警告」句式。把观点写成你自己的判断。"
        )
        try:
            output = call_llm(
                prompt=fix_prompt,
                provider=llm_cfg.get("provider", "openai"),
                model=llm_cfg.get("model", "gpt-4o"),
                api_key_env=llm_cfg.get("api_key_env", "OPENAI_API_KEY"),
                base_url=llm_cfg.get("base_url"),
                temperature=max(0.2, llm_cfg.get("temperature", 0.4) - 0.1),
                max_tokens=llm_cfg.get("max_tokens", 2500),
            )
            validation = validate(output)
        except Exception as e:
            print(f"LLM retry failed: {e}", file=sys.stderr)
            return 1

    # 6. Validate
    if not validation["ok"]:
        print(f"Validation failed: {validation['errors']}", file=sys.stderr)
        # Still write raw output for debugging
        debug_file = cache_dir / f"raw_output_{today_date}.txt"
        debug_file.write_text(output, encoding="utf-8")
        print(f"Raw output saved to: {debug_file}", file=sys.stderr)
        return 1

    if validation["warnings"]:
        print(f"Validation warnings: {validation['warnings']}", file=sys.stderr)

    # 7. Write output
    output_file.write_text(output, encoding="utf-8")
    print(f"Briefing written to: {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
