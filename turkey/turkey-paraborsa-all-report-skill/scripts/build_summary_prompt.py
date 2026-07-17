#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build LLM prompt for Part 1 summary section."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from build_concat import article_type_label, broker_display_name
from extract_tickers import extract_tickers, tickers_by_article


def _excerpt(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...（后文略）"


def build_material_block(articles: list[dict], excerpt_chars: int) -> str:
    lines: list[str] = []
    for idx, art in enumerate(articles, 1):
        if art.get("fetch_status") != "ok":
            continue
        broker = broker_display_name(art)
        atype = article_type_label(art)
        tickers = extract_tickers(art.get("content", ""))
        lines.append(f"### 素材 {idx}：{broker}（{atype}）")
        lines.append(f"标题：{art.get('title', '')}")
        lines.append(f"链接：{art.get('url', '')}")
        lines.append(f"自动识别标的：{', '.join(tickers) if tickers else '（无）'}")
        lines.append("")
        lines.append(_excerpt(art.get("content", ""), excerpt_chars))
        lines.append("")
    return "\n".join(lines)


def build_ticker_index(articles: list[dict]) -> str:
    by_broker = tickers_by_article(articles)
    ticker_to_brokers: dict[str, list[str]] = {}
    for broker, tickers in by_broker.items():
        display = broker.replace("-", " ").title()
        for t in tickers:
            ticker_to_brokers.setdefault(t, []).append(display)
    if not ticker_to_brokers:
        return "（未自动识别到 BIST 标的）"
    lines = ["| 标的 | 提及券商 |", "|---|---|"]
    for ticker in sorted(ticker_to_brokers):
        brokers = "、".join(sorted(set(ticker_to_brokers[ticker])))
        lines.append(f"| {ticker} | {brokers} |")
    return "\n".join(lines)


def build_prompt(
    template_path: Path,
    target_date: date,
    weekday_cn: str,
    articles: list[dict],
    *,
    excerpt_chars: int = 5000,
) -> str:
    template = template_path.read_text(encoding="utf-8")
    ok_count = sum(1 for a in articles if a.get("fetch_status") == "ok")
    return (
        template.replace("{target_date}", target_date.isoformat())
        .replace("{weekday_cn}", weekday_cn)
        .replace("{article_count}", str(len(articles)))
        .replace("{fetched_ok_count}", str(ok_count))
        .replace("{ticker_index}", build_ticker_index(articles))
        .replace("{material_block}", build_material_block(articles, excerpt_chars))
    )
