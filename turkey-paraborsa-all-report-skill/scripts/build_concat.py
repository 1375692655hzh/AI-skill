#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Part 2: concatenated broker commentary bodies."""
from __future__ import annotations

from datetime import date

WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def broker_display_name(article: dict) -> str:
    title = article.get("title", "")
    if " / " in title:
        part = title.split(" / ", 1)[1]
        part = part.split("–", 1)[0].split("-", 1)[0].strip()
        if part:
            return part
    slug = article.get("broker_slug", "")
    return slug.replace("-", " ").title() if slug else "Unknown"


def article_type_label(article: dict) -> str:
    mapping = {
        "borsa-yorumu": "Borsa Yorumu",
        "gun-ici-borsa-yorumu": "Gün İçi Borsa Yorumu",
        "viop-yorumu": "VİOP Yorumu",
        "haftalik-borsa-yorumu": "Haftalık Borsa Yorumu",
    }
    return mapping.get(article.get("article_type", ""), article.get("article_type", "Yorum"))


def build_concat_section(target_date: date, articles: list[dict]) -> str:
    weekday_cn = WEEKDAYS_CN[target_date.weekday()]
    lines = [
        f"【拼接内容 — {target_date.isoformat()}（{weekday_cn}）】",
        f"共收录 {sum(1 for a in articles if a.get('fetch_status') == 'ok')} 篇正文；"
        f"发现 {len(articles)} 篇候选。",
        "",
    ]
    seq = 0
    for art in articles:
        if art.get("fetch_status") != "ok":
            continue
        seq += 1
        broker = broker_display_name(art)
        atype = article_type_label(art)
        lines.append(f"--- 第{seq}篇 | {broker} | {atype} ---")
        lines.append(f"标题：{art.get('title', '')}")
        lines.append(f"链接：{art.get('url', '')}")
        lines.append("")
        lines.append(art.get("content", "").strip())
        lines.append("")
        lines.append("")
    for art in articles:
        if art.get("fetch_status") == "ok":
            continue
        broker = broker_display_name(art)
        lines.append(f"--- 未抓到正文 | {broker} | {article_type_label(art)} ---")
        lines.append(f"标题：{art.get('title', '')}")
        lines.append(f"链接：{art.get('url', '')}")
        lines.append(f"状态：{art.get('fetch_status', 'unknown')}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
