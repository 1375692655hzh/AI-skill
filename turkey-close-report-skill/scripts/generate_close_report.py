#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main entry: generate Turkey close-of-day report."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from build_prompt import build_prompt
from call_llm import call_llm
from check_source_date import is_content_for_date
from fetch_bloomberght import fetch_close_review
from fetch_info_yatirim import fetch_info_yatirim
from fetch_paraborsa import fetch_paraborsa
from resolve_target_date import resolve_target_date, today_tr, is_trading_day_open
from validate_output import validate


WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def format_bloomberght(data: dict) -> str:
    lines = []
    if data.get("closing_review", {}).get("text"):
        lines.append("【BloombergHT 详细收盘】")
        lines.append(data["closing_review"]["text"][:8000])
    if data.get("breaking_news"):
        lines.append("\n【BloombergHT 突发新闻】")
        for n in data["breaking_news"]:
            lines.append(f"- {n}")
    if data.get("featured_news"):
        lines.append("\n【BloombergHT 重点新闻】")
        for n in data["featured_news"]:
            lines.append(f"- {n}")
    return "\n".join(lines)


def format_paraborsa(data: dict) -> str:
    if not data.get("selected"):
        return "暂无券商评论数据。"
    sel = data["selected"]
    return f"标题：{sel.get('title', '')}\nURL：{sel.get('url', '')}\n\n内容：\n{sel.get('content', '')[:8000]}"


def format_info_yatirim(data: dict) -> str:
    lines = []
    if data.get("daily", {}).get("content"):
        lines.append("【每日公告】")
        lines.append(data["daily"]["content"][:5000])
    if data.get("technical", {}).get("content"):
        lines.append("\n【技术分析】")
        lines.append(data["technical"]["content"][:5000])
    return "\n".join(lines) if lines else "暂无 Info Yatırım 数据。"


def generate(config_path: Path, force_date: str | None = None, no_llm: bool = False) -> Path | None:
    config = load_config(config_path)
    workdir = Path(config["workdir"]).expanduser()
    output_dir = workdir / config["output_dir"]
    cache_dir = workdir / config["cache_dir"]
    template_path = Path(config["template_path"])
    if not template_path.is_absolute():
        template_path = config_path.parent / template_path

    holidays = config.get("holidays", [])
    target_date = resolve_target_date(force_date, holidays)
    today = today_tr()

    # Close report should be generated for a business day
    if not is_trading_day_open(target_date, holidays):
        print(f"Target date {target_date} is a weekend or holiday. Skip.")
        return None

    print(f"Today (TR): {today}")
    print(f"Target date: {target_date}")

    # 1. Fetch BloombergHT close review
    bloomberght = fetch_close_review(target_date, cache_dir, workdir=workdir)
    closing_text = bloomberght.get("closing_review", {}).get("text", "")
    if closing_text and not is_content_for_date(target_date, closing_text, "bloomberght"):
        print(f"Warning: BloombergHT closing review date mismatch, discarding cache for {target_date}")
        cache_file = cache_dir / f"bloomberght_close_{target_date.isoformat()}.json"
        if cache_file.exists():
            cache_file.unlink()
        bloomberght = fetch_close_review(target_date, cache_dir, workdir=workdir)
    if not bloomberght.get("ok"):
        print(f"Warning: BloombergHT closing review not found for {target_date}")

    # 2. Fetch Paraborsa broker commentary
    paraborsa = fetch_paraborsa(target_date, cache_dir)
    selected_content = paraborsa.get("selected", {}).get("content", "")
    selected_title = paraborsa.get("selected", {}).get("title", "")
    if selected_content and not is_content_for_date(
        target_date, selected_title + " " + selected_content, "paraborsa"
    ):
        print(f"Warning: Paraborsa commentary date mismatch, discarding cache for {target_date}")
        cache_file = cache_dir / f"paraborsa_{target_date.isoformat()}.json"
        if cache_file.exists():
            cache_file.unlink()
        paraborsa = fetch_paraborsa(target_date, cache_dir)

    # 3. Fetch Info Yatirim bulletins
    info_yatirim = fetch_info_yatirim(target_date, cache_dir)
    daily_content = info_yatirim.get("daily", {}).get("content", "")
    technical_content = info_yatirim.get("technical", {}).get("content", "")
    if daily_content and not is_content_for_date(target_date, daily_content, "info_yatirim"):
        print(f"Warning: Info Yatırım daily bulletin date mismatch, discarding cache for {target_date}")
        cache_file = cache_dir / f"info_yatirim_{target_date.isoformat()}.json"
        if cache_file.exists():
            cache_file.unlink()
        info_yatirim = fetch_info_yatirim(target_date, cache_dir)

    # 4. Build prompt
    weekday_cn = WEEKDAYS_CN[target_date.weekday()]
    prompt = build_prompt(
        template_path=template_path,
        today_date=target_date.isoformat(),
        target_date=target_date.isoformat(),
        weekday_cn=weekday_cn,
        bloomberght_text=format_bloomberght(bloomberght),
        paraborsa_text=format_paraborsa(paraborsa),
        info_yatirim_text=format_info_yatirim(info_yatirim),
    )

    prompt_file = cache_dir / f"close_prompt_{target_date.isoformat()}.txt"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt, encoding="utf-8")
    print(f"Prompt saved to: {prompt_file}")

    if no_llm:
        return prompt_file

    # 5. Call LLM
    llm_cfg = config["llm"]
    api_key_env = llm_cfg.get("api_key") or llm_cfg.get("api_key_env", "OPENAI_API_KEY")
    content = call_llm(
        prompt=prompt,
        provider=llm_cfg["provider"],
        model=llm_cfg["model"],
        api_key_env=api_key_env,
        base_url=llm_cfg.get("base_url"),
        temperature=llm_cfg.get("temperature", 0.4),
        max_tokens=llm_cfg.get("max_tokens", 4000),
    )

    # 6. Validate
    result = validate(content)
    if not result["ok"]:
        raw_output = cache_dir / f"close_raw_output_{target_date.isoformat()}.txt"
        raw_output.write_text(content, encoding="utf-8")
        print(f"Validation failed: {result['errors']}")
        print(f"Raw output saved to: {raw_output}")
        return None

    # 7. Write output
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{target_date.isoformat()}_close_report_zh.txt"
    output_file.write_text(content, encoding="utf-8")
    print(f"Close report written to: {output_file}")
    return output_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Turkey close-of-day report")
    parser.add_argument("--config", type=Path, required=True, help="Path to config.json")
    parser.add_argument("--force-date", type=str, default=None, help="Force target date (YYYY-MM-DD)")
    parser.add_argument("--no-llm", action="store_true", help="Only build prompt, do not call LLM")
    args = parser.parse_args()

    try:
        generate(args.config, force_date=args.force_date, no_llm=args.no_llm)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
