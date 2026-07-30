# -*- coding: utf-8 -*-
"""Build a metadata header listing data sources and fetch status.

Appended to the top of generated reports so readers can see at a glance
which sources were used, their URLs, and whether each fetch succeeded.
Mirrors the provenance block the AA morning-briefing skill has always
emitted; other Turkey skills adopt the same pattern via this helper.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Iterable, Optional

TR_TZ = timezone(timedelta(hours=3))
BJ_TZ = timezone(timedelta(hours=8))

_SEPARATOR = "=" * 72


def now_stamp() -> str:
    """Return 'YYYY-MM-DD HH:MM (TR ...) (BJ ...)' for the current instant."""
    now = datetime.now(TR_TZ)
    tr = now.strftime("%Y-%m-%d %H:%M")
    bj = now.astimezone(BJ_TZ).strftime("%H:%M")
    return f"{tr} (TR) / {bj} (BJ)"


def _format_source(src: dict) -> str:
    """Render one source line. src keys: name, url, status ('ok'|'fail'),
    detail (optional human-readable note)."""
    name = src.get("name", "未命名源")
    status = src.get("status", "unknown")
    detail = src.get("detail") or ""
    url = src.get("url") or ""

    if status == "ok":
        status_cn = "成功"
    elif status in ("fail", "failed", "error"):
        status_cn = "失败"
    elif status == "partial":
        status_cn = "部分"
    else:
        status_cn = str(status)

    parts = [f"- {name}：{status_cn}"]
    if detail:
        parts.append(detail)
    if url:
        parts.append(f"— {url}")
    return " ".join(parts)


def build_source_header(
    sources: Iterable[dict],
    *,
    title: Optional[str] = None,
    generated_at: Optional[str] = None,
) -> str:
    """Assemble the header block that prefixes report bodies.

    sources: iterable of dicts with keys {name, url, status, detail}.
    title: optional first line (e.g. report name + date).
    generated_at: optional override of the generation timestamp string.
    Returns the header text WITHOUT trailing body — caller concatenates body.
    """
    lines: list[str] = []
    if title:
        lines.append(title)
        lines.append("")
    stamp = generated_at or now_stamp()
    lines.append(f"数据来源｜抓取于 {stamp}")
    for src in sources:
        lines.append(_format_source(src))
    lines.append(_SEPARATOR)
    lines.append("")
    return "\n".join(lines)


def prepend_header(body: str, sources: Iterable[dict], **kwargs) -> str:
    """Convenience: build header + concatenate body with exactly one blank line."""
    header = build_source_header(sources, **kwargs)
    body = (body or "").lstrip("\n")
    return header + body
