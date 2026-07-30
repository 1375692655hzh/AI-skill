#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main orchestration: generate the Turkish morning briefing."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from build_brief_prompt import build_brief_prompt
from build_prompt import build_prompt
from bht_fact_sheet import format_closing_for_morning_prompt
from fetch_bloomberght_closing import fetch_closing_review, fetch_today_headlines
from fetch_live_quotes import fetch_live_quotes
from fetch_news import fetch_news
from llm_runner import generate_brief_with_retry, generate_with_validation
from resolve_target_date import resolve_dates
from runtime_utils import configure_stdio, resolve_paths
from source_header import prepend_header
from fetch_aa_top_stories import fetch_aa_top_stories
from news_fact_sheet import build_international_news_card
from validate_brief_output import validate_brief
from validate_output import validate


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def resolve_brief_template(skill_dir: Path, config: dict) -> Path | None:
    brief_cfg = config.get("brief", {})
    if not brief_cfg.get("enabled", True):
        return None
    rel = brief_cfg.get("template_path", "templates/morning_briefing_brief_template.txt")
    candidates = [skill_dir / rel, Path(__file__).resolve().parent.parent / rel]
    for path in candidates:
        if path.is_file():
            return path
    return None


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

    output_file = output_dir / f"{today_date}_daily_briefing_zh.md"
    brief_file = output_dir / f"{today_date}_daily_briefing_brief_zh.md"

    closing_cfg = config.get("sources", {}).get("bloomberght_closing", {})
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

    live = fetch_live_quotes(cache_dir)
    if not live.get("ok"):
        print(f"Warning: live quotes fetch failed: {live.get('error')}", file=sys.stderr)
    closing_material = format_closing_for_morning_prompt(
        closing_text if closing.get("ok") else "",
        live_fact_cn=live.get("fact_cn") or "",
        live_quotes=live,
    )

    news_cfg = config.get("sources", {}).get("news", {})
    news = fetch_news(
        target_date=date.fromisoformat(target_date),
        cache_dir=cache_dir,
        news_cfg=news_cfg,
        workdir=workdir,
        closing_cfg=closing_cfg,
    )

    news_parts = []
    # 国际/突发只用「今日(TR)」：禁止复用昨收缓存里的 SON DAKİKA / 旧重点稿
    today_headlines = fetch_today_headlines(date.fromisoformat(today_date))
    breaking = today_headlines.get("breaking_news", [])
    featured = today_headlines.get("featured_news", [])
    # persist for audit (do not mix into yesterday's bloomberght_all cache)
    (cache_dir / f"bht_today_headlines_{today_date}.json").write_text(
        json.dumps(
            {
                "ok": True,
                "today_date": today_date,
                "breaking_news": breaking,
                "featured_news": featured,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    aa_cfg = news_cfg.get("aa_morning", {})
    aa_titles: list[str] = []
    aa: dict = {"ok": False, "titles": [], "error": ""}
    if aa_cfg.get("enabled", True):
        aa = fetch_aa_top_stories(
            date.fromisoformat(today_date),
            cache_dir,
            aa_skill_dir=aa_cfg.get("skill_dir"),
        )
        if aa.get("ok"):
            aa_titles = list(aa.get("titles") or [])
            print(f"AA TOP STORIES: {len(aa_titles)} titles", file=sys.stderr)
        else:
            print(f"Warning: AA TOP STORIES unavailable: {aa.get('error')}", file=sys.stderr)

    news_limit = int(aa_cfg.get("news_limit", news_cfg.get("international_limit", 3)))
    news_card = build_international_news_card(
        breaking,
        featured,
        aa_titles=aa_titles,
        limit=news_limit,
    )
    news_parts.append(news_card)

    if breaking:
        news_parts.append(f"\n【今日突发原题｜{today_date}｜仅供核对，正文禁止署名】")
        for item in breaking[:12]:
            news_parts.append(item.get("title", "") if isinstance(item, dict) else str(item))
    if featured:
        news_parts.append(f"\n【今日重点原题｜{today_date}｜仅供核对，正文禁止署名】")
        for item in featured[:12]:
            news_parts.append(item.get("title", "") if isinstance(item, dict) else str(item))
    if aa_titles:
        news_parts.append(f"\n【AA今日重要资讯｜{today_date}｜TOP STORIES，仅供核对，正文禁止署名】")
        for t in aa_titles[:8]:
            news_parts.append(t)
    if not breaking and not featured and not aa_titles:
        if news["web_search"]["results"]:
            for item in news["web_search"]["results"]:
                news_parts.append(f"{item.get('title', '')}: {item.get('snippet', '')}")
        if news["x_search"]["results"]:
            for item in news["x_search"]["results"]:
                news_parts.append(f"{item.get('title', '')}: {item.get('snippet', '')}")

    news_text = "\n".join(news_parts) if news_parts else "（无补充新闻数据）"

    prompt = build_prompt(
        template_path=template_path,
        today_date=today_date,
        target_date=target_date,
        closing_text=closing_material,
        news_text=news_text,
    )

    if args.no_llm:
        prompt_file = cache_dir / f"prompt_{today_date}.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        print(f"Prompt saved to: {prompt_file}")
        return 0

    llm_cfg = config["llm"]
    output, validation = generate_with_validation(prompt, llm_cfg, validate)
    if output is None or not validation["ok"]:
        print(f"Validation failed: {validation.get('errors', [])}", file=sys.stderr)
        if output:
            debug_file = cache_dir / f"raw_output_{today_date}.txt"
            debug_file.write_text(output, encoding="utf-8")
            print(f"Raw output saved to: {debug_file}", file=sys.stderr)
        return 1

    if validation.get("warnings"):
        print(f"Validation warnings: {validation['warnings']}", file=sys.stderr)

    # 只要换行、不要空行
    output = re.sub(r"\n{2,}", "\n", output.replace("\r\n", "\n")).strip() + "\n"

    # 数据来源元数据：每个抓取源的 URL + 状态
    cr = (closing.get("closing_review") or {}) if closing.get("ok") else {}
    bht_url = cr.get("url") or "https://www.bloomberght.com/borsa/kapanis"
    bht_detail = ""
    if cr.get("article_id"):
        bht_detail = f"文章 id={cr['article_id']}"
    elif closing.get("ok"):
        bht_detail = "已抓取前一交易日收盘综述"
    xu = (live.get("quotes") or {}).get("XU100") or {}
    xu_status = live.get("xu100_status") or ""
    xu_detail = f"XU100={xu.get('last')} ({xu.get('pct')}%) [{xu_status}]" if xu else ""
    break_n = len(breaking) if isinstance(breaking, list) else 0
    feat_n = len(featured) if isinstance(featured, list) else 0
    sources = [
        {
            "name": "BHT 收评文章（前一交易日）",
            "url": bht_url,
            "status": "ok" if closing.get("ok") else "fail",
            "detail": bht_detail or (closing.get("error") or ""),
        },
        {
            "name": "BHT 实时行情 /piyasalar",
            "url": "https://www.bloomberght.com/piyasalar",
            "status": "ok" if live.get("ok") else "fail",
            "detail": xu_detail or (live.get("error") or ""),
        },
        {
            "name": "BHT 今日头条",
            "url": "https://www.bloomberght.com/sondakika",
            "status": "ok" if (break_n or feat_n) else "fail",
            "detail": f"突发 {break_n} 条 / 重点 {feat_n} 条",
        },
        {
            "name": "AA TOP STORIES",
            "url": aa.get("url") or "https://www.aa.com.tr/en/world",
            "status": "ok" if aa.get("ok") else "fail",
            "detail": (f"{len(aa_titles)} 条" if aa_titles else "") or (aa.get("error") or ""),
        },
    ]
    title = f"土耳其股市早评 — {today_date}"
    output = prepend_header(output, sources, title=title)

    output_file.write_text(output, encoding="utf-8")
    print(f"Briefing written to: {output_file}")

    brief_template = resolve_brief_template(skill_dir, config)
    if brief_template:
        brief_cfg = config.get("brief", {})
        brief_prompt = build_brief_prompt(brief_template, today_date, output)
        brief_llm_cfg = {
            **llm_cfg,
            "max_tokens": brief_cfg.get("max_tokens", 1200),
            "temperature": brief_cfg.get("temperature", 0.3),
        }
        brief_output, brief_validation = generate_brief_with_retry(
            brief_prompt,
            brief_llm_cfg,
            lambda text: validate_brief(
                text,
                min_chars=brief_cfg.get("min_chars", 200),
                max_chars=brief_cfg.get("max_chars", 520),
            ),
            fix_hint=(
                "首行必须是【土耳其股市早报简报 — 日期】；"
                "字段顺序固定：【指数】【汇率】【驱动】【个股】【板块】【操作】【风险】；"
                "【个股】标签独占一行，其后 3–5 只个股，每只一行，格式「代码 涨跌/要点」；"
                "禁止列表符号、Markdown、表格、Emoji；"
                "篇幅 200–520 个汉字+中文标点（英文代码、数字不计入）；"
                "只要换行、不要空行。"
            ),
        )
        if brief_output and brief_validation.get("ok"):
            brief_file.write_text(brief_output, encoding="utf-8")
            print(f"Brief briefing written to: {brief_file}")
            if brief_validation.get("warnings"):
                print(f"Brief warnings (non-blocking): {brief_validation['warnings']}", file=sys.stderr)
        else:
            print(f"Brief validation failed: {brief_validation.get('errors', [])}", file=sys.stderr)
            if brief_output:
                debug_brief = cache_dir / f"raw_brief_{today_date}.txt"
                debug_brief.write_text(brief_output, encoding="utf-8")
                print(f"Raw brief saved to: {debug_brief}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
