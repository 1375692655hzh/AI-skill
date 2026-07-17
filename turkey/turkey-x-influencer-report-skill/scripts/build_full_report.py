#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build full original+translation report text."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any


WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _fmt_metrics(m: dict) -> str:
    if not m:
        return ""
    parts = []
    if m.get("views"):
        parts.append(f"浏览 {m['views']}")
    if m.get("likes"):
        parts.append(f"点赞 {m['likes']}")
    if m.get("retweets"):
        parts.append(f"转发 {m['retweets']}")
    if m.get("replies"):
        parts.append(f"回复 {m['replies']}")
    return " · ".join(parts)


def build_full_report(
    target_date: date,
    posts: list[dict[str, Any]],
    meta: dict[str, Any],
) -> str:
    weekday = WEEKDAYS_CN[target_date.weekday()]
    window_label = meta.get("window_label") or (
        f"TR 昨天 00:00 → 现在（约 {meta.get('hours', '?')}h）"
        if meta.get("window") == "yesterday_start_to_now"
        else f"近 {meta.get('hours', 24)} 小时"
    )
    lines = [
        f"【推特大V全文 — {target_date.isoformat()}（{weekday}）】",
        f"窗口：{window_label} | 账号数：{len(meta.get('accounts') or [])} | 帖子数：{len(posts)}",
        f"Since (UTC)：{meta.get('since', '')}",
        f"Until (UTC)：{meta.get('until', '')}",
        "说明：原文 verbatim；译文由 LLM 生成，金融术语/ticker 保留英文。媒体链接附于原文后。",
        "",
        "=" * 72,
        "",
    ]

    failures = meta.get("failures") or []
    if failures:
        lines.append("【抓取失败账号】")
        for f in failures:
            lines.append(f"- {f.get('handle')}: {f.get('error')}")
        lines.append("")

    by_account: dict[str, list[dict]] = defaultdict(list)
    order: list[str] = []
    for p in posts:
        key = p.get("account") or "?"
        if key not in by_account:
            order.append(key)
        by_account[key].append(p)

    if not posts:
        lines.append("（窗口内无抓取到帖子）")
        lines.append("")
        return "\n".join(lines)

    for handle in order:
        group = by_account[handle]
        name = group[0].get("account_name") or handle
        lines.append(f"## {name} ({handle})")
        lines.append("")
        for i, post in enumerate(group, 1):
            ts = post.get("created_at") or post.get("raw_time") or "时间未知"
            metrics = _fmt_metrics(post.get("metrics") or {})
            header = f"### {i}. {ts}"
            if metrics:
                header += f" · {metrics}"
            if post.get("is_retweet"):
                header += " · 转发"
            lines.append(header)
            if post.get("url"):
                lines.append(f"链接：{post['url']}")
            lines.append("")
            lines.append("【原文】")
            lines.append((post.get("text") or "").strip() or "（空）")
            media = post.get("media") or []
            if media:
                lines.append("")
                lines.append("【媒体】")
                for murl in media:
                    lines.append(f"- {murl}")
            lines.append("")
            lines.append("【译文】")
            lines.append((post.get("translation") or "").strip() or "（无译文）")
            if post.get("quoted_text"):
                lines.append("")
                qh = (post.get("quoted_handle") or "").lstrip("@")
                lines.append(f"【引用原帖】@{qh}" if qh else "【引用原帖】")
                lines.append(post["quoted_text"].strip())
                if post.get("quoted_translation"):
                    lines.append("【引用译文】")
                    lines.append(post["quoted_translation"].strip())
            lines.append("")
            lines.append("-" * 40)
            lines.append("")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
