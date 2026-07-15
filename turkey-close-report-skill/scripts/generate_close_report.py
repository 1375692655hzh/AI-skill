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

sys.path.insert(0, str(Path(__file__).parent))

from build_prompt import build_prompt
from call_llm import call_llm
from check_source_date import is_content_for_date
from fetch_bloomberght import fetch_close_review
from fetch_info_yatirim import fetch_info_yatirim
from fetch_paraborsa import fetch_paraborsa
from resolve_target_date import resolve_target_date, today_tr, is_trading_day_open
from runtime_utils import configure_stdio, resolve_paths
from validate_output import validate


WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def format_bloomberght(data: dict) -> str:
    lines = []
    if data.get("closing_review", {}).get("text"):
        lines.append("【收盘数据】")
        lines.append(data["closing_review"]["text"][:8000])
    if data.get("breaking_news"):
        lines.append("\n【盘中突发】")
        for title in data["breaking_news"]:
            lines.append(title)
    if data.get("featured_news"):
        lines.append("\n【重点资讯】")
        for title in data["featured_news"]:
            lines.append(title)
    return "\n".join(lines)


def format_paraborsa(data: dict) -> str:
    if not data.get("selected"):
        return "暂无市场观点数据。"
    sel = data["selected"]
    return f"{sel.get('content', '')[:8000]}"


def format_info_yatirim(data: dict) -> str:
    lines = []
    if data.get("daily", {}).get("content"):
        lines.append("【每日公告】")
        lines.append(data["daily"]["content"][:5000])
    if data.get("technical", {}).get("content"):
        lines.append("\n【技术分析】")
        lines.append(data["technical"]["content"][:5000])
    return "\n".join(lines) if lines else "暂无技术/公告数据。"


def generate(config_path: Path, force_date: str | None = None, no_llm: bool = False) -> Path | None:
    configure_stdio()
    config = load_config(config_path)
    _, workdir, output_dir, cache_dir, template_path = resolve_paths(
        config_path,
        config,
        default_template="templates/close_report_template.txt",
        default_cache=".cache/turkey-close-report",
    )
    os.chdir(workdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not template_path.is_file():
        print(f"Template not found: {template_path}", file=sys.stderr)
        return None

    holidays = config.get("holidays", [])
    target_date = resolve_target_date(force_date, holidays)
    today = today_tr()
    use_project_fetcher = config.get("sources", {}).get("bloomberght_closing", {}).get(
        "use_project_fetcher", False
    )

    if not is_trading_day_open(target_date, holidays):
        print(f"Target date {target_date} is a weekend or holiday. Skip.")
        return None

    print(f"Today (TR): {today}")
    print(f"Target date: {target_date}")

    bloomberght = fetch_close_review(
        target_date,
        cache_dir,
        workdir=workdir,
        use_project_fetcher=use_project_fetcher,
    )
    closing_text = bloomberght.get("closing_review", {}).get("text", "")
    if closing_text and not is_content_for_date(target_date, closing_text, "bloomberght"):
        print(f"Warning: closing review date mismatch, discarding cache for {target_date}")
        cache_file = cache_dir / f"bloomberght_close_{target_date.isoformat()}.json"
        if cache_file.exists():
            cache_file.unlink()
        bloomberght = fetch_close_review(
            target_date,
            cache_dir,
            workdir=workdir,
            use_project_fetcher=use_project_fetcher,
        )
    if not bloomberght.get("ok"):
        print(f"Warning: closing review not found for {target_date}")

    paraborsa = fetch_paraborsa(target_date, cache_dir)
    selected_content = paraborsa.get("selected", {}).get("content", "")
    selected_title = paraborsa.get("selected", {}).get("title", "")
    if selected_content and not is_content_for_date(
        target_date, selected_title + " " + selected_content, "paraborsa"
    ):
        print(f"Warning: commentary date mismatch, discarding cache for {target_date}")
        cache_file = cache_dir / f"paraborsa_{target_date.isoformat()}.json"
        if cache_file.exists():
            cache_file.unlink()
        paraborsa = fetch_paraborsa(target_date, cache_dir)

    info_yatirim = fetch_info_yatirim(target_date, cache_dir)
    daily_content = info_yatirim.get("daily", {}).get("content", "")
    if daily_content and not is_content_for_date(target_date, daily_content, "info_yatirim"):
        print(f"Warning: bulletin date mismatch, discarding cache for {target_date}")
        cache_file = cache_dir / f"info_yatirim_{target_date.isoformat()}.json"
        if cache_file.exists():
            cache_file.unlink()
        info_yatirim = fetch_info_yatirim(target_date, cache_dir)

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
    prompt_file.write_text(prompt, encoding="utf-8")
    print(f"Prompt saved to: {prompt_file}")

    if no_llm:
        return prompt_file

    llm_cfg = config["llm"]
    api_key_env = llm_cfg.get("api_key") or llm_cfg.get("api_key_env", "OPENAI_API_KEY")
    try:
        content = call_llm(
            prompt=prompt,
            provider=llm_cfg["provider"],
            model=llm_cfg["model"],
            api_key_env=api_key_env,
            base_url=llm_cfg.get("base_url"),
            temperature=llm_cfg.get("temperature", 0.4),
            max_tokens=llm_cfg.get("max_tokens", 4000),
        )
    except Exception as exc:
        print(f"LLM call failed: {exc}", file=sys.stderr)
        return None

    result = validate(content)
    if not result["ok"] and result.get("attribution_hits"):
        fix_prompt = (
            prompt
            + "\n\n【重要修订】你上一版草稿仍出现了来源署名（如券商、平台、研究机构名称）。"
            "请完全重写：正文不得出现任何机构/平台/网站/报告名称，"
            "也不得使用「某某指出/认为/提示/警告」句式。把观点写成你自己的判断。"
        )
        try:
            content = call_llm(
                prompt=fix_prompt,
                provider=llm_cfg["provider"],
                model=llm_cfg["model"],
                api_key_env=api_key_env,
                base_url=llm_cfg.get("base_url"),
                temperature=max(0.2, llm_cfg.get("temperature", 0.4) - 0.1),
                max_tokens=llm_cfg.get("max_tokens", 4000),
            )
            result = validate(content)
        except Exception as exc:
            print(f"LLM retry failed: {exc}", file=sys.stderr)
            return None

    if not result["ok"]:
        raw_output = cache_dir / f"close_raw_output_{target_date.isoformat()}.txt"
        raw_output.write_text(content, encoding="utf-8")
        print(f"Validation failed: {result['errors']}")
        print(f"Raw output saved to: {raw_output}")
        return None

    if result["warnings"]:
        print(f"Validation warnings: {result['warnings']}")

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
