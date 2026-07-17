#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build LLM prompt for curated investment digest."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any


WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _post_block(post: dict[str, Any], excerpt: int) -> str:
    text = (post.get("text") or "").strip()
    tr = (post.get("translation") or "").strip()
    if len(text) > excerpt:
        text = text[: excerpt - 1] + "…"
    if len(tr) > excerpt:
        tr = tr[: excerpt - 1] + "…"
    lines = [
        f"账号：{post.get('account_name') or ''} ({post.get('account')})",
        f"时间：{post.get('created_at') or post.get('raw_time') or '未知'}",
        f"链接：{post.get('url') or ''}",
        f"原文：{text}",
        f"译文：{tr}",
    ]
    if post.get("quoted_text"):
        q = post["quoted_text"]
        if len(q) > excerpt:
            q = q[: excerpt - 1] + "…"
        lines.append(f"引用：{q}")
    return "\n".join(lines)


def build_curated_prompt(
    template_path: Path,
    target_date: date,
    posts: list[dict[str, Any]],
    *,
    excerpt_chars: int = 600,
    max_posts: int = 80,
) -> str:
    template = template_path.read_text(encoding="utf-8")
    selected = posts[:max_posts]
    blocks = []
    for i, post in enumerate(selected, 1):
        blocks.append(f"----- 帖子 {i} -----\n{_post_block(post, excerpt_chars)}")
    posts_block = "\n\n".join(blocks) if blocks else "（无帖子）"
    return (
        template.replace("{date}", target_date.isoformat())
        .replace("{weekday}", WEEKDAYS_CN[target_date.weekday()])
        .replace("{posts_block}", posts_block)
    )
