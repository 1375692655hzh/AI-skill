#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reorder AA Morning Briefing sections: move NEWS IN BRIEF to the bottom."""
from __future__ import annotations

import re
from typing import List, Tuple


# Canonical section titles (page may include zero-width chars around NEWS IN BRIEF)
SECTION_ALIASES = {
    "TOP STORIES": "TOP STORIES",
    "NEWS IN BRIEF": "NEWS IN BRIEF",
    "BUSINESS & ECONOMY": "BUSINESS & ECONOMY",
    "BUSINESS AND ECONOMY": "BUSINESS & ECONOMY",
    "SPORTS": "SPORTS",
}

# Preferred output order: NEWS IN BRIEF always last among known sections
PREFERRED_ORDER = [
    "TOP STORIES",
    "BUSINESS & ECONOMY",
    "SPORTS",
    "NEWS IN BRIEF",
]


def _normalize_header(line: str) -> str | None:
    cleaned = re.sub(r"[\u200b\u200c\u200d\ufeff\xa0]+", "", line or "")
    cleaned = cleaned.strip()
    if not cleaned:
        return None
    # Strip leading bullets / markdown markers
    cleaned = re.sub(r"^[-*•\d.\s]+", "", cleaned).strip()
    key = re.sub(r"\s+", " ", cleaned).upper()
    return SECTION_ALIASES.get(key)


def split_sections(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Split body into (intro, [(section_name, section_body), ...]).
    Section headers must appear on their own line.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    intro_lines: List[str] = []
    sections: List[Tuple[str, List[str]]] = []
    current_name: str | None = None
    current_body: List[str] = []

    for line in lines:
        header = _normalize_header(line)
        if header:
            if current_name is None:
                intro_lines = current_body[:]
            else:
                sections.append((current_name, current_body))
            current_name = header
            current_body = []
            continue
        current_body.append(line)

    if current_name is None:
        return "\n".join(lines).strip(), []
    sections.append((current_name, current_body))

    normalized: List[Tuple[str, str]] = []
    for name, body_lines in sections:
        body = "\n".join(body_lines).strip()
        normalized.append((name, body))
    return "\n".join(intro_lines).strip(), normalized


def reorder_news_in_brief_last(text: str) -> str:
    """
    Keep full original wording; only move NEWS IN BRIEF block to the end.
    Unknown sections keep relative order and stay before NEWS IN BRIEF.
    """
    intro, sections = split_sections(text)
    if not sections:
        return text.strip()

    by_name: dict[str, str] = {}
    unknown: List[Tuple[str, str]] = []
    seen_order: List[str] = []

    for name, body in sections:
        if name in SECTION_ALIASES.values():
            if name not in by_name:
                seen_order.append(name)
            # If duplicate headers appear, append bodies
            if name in by_name and by_name[name]:
                by_name[name] = by_name[name] + "\n\n" + body
            else:
                by_name[name] = body
        else:
            unknown.append((name, body))

    ordered_names: List[str] = []
    for name in PREFERRED_ORDER:
        if name in by_name and name != "NEWS IN BRIEF":
            ordered_names.append(name)
    # Any known section not in preferred list (future-proof)
    for name in seen_order:
        if name not in ordered_names and name != "NEWS IN BRIEF":
            ordered_names.append(name)

    parts: List[str] = []
    if intro:
        parts.append(intro)

    for name in ordered_names:
        body = by_name.get(name, "").strip()
        block = name if not body else f"{name}\n\n{body}"
        parts.append(block)

    for name, body in unknown:
        body = body.strip()
        block = name if not body else f"{name}\n\n{body}"
        parts.append(block)

    if "NEWS IN BRIEF" in by_name:
        body = by_name["NEWS IN BRIEF"].strip()
        block = "NEWS IN BRIEF" if not body else f"NEWS IN BRIEF\n\n{body}"
        parts.append(block)

    return "\n\n".join(parts).strip() + "\n"


if __name__ == "__main__":
    sample = (
        "Intro paragraph.\n\n"
        "TOP STORIES\n\nA\n\n"
        "​​​​​​​NEWS IN BRIEF\n\n- b1\n\n"
        "BUSINESS & ECONOMY\n\nC\n\n"
        "SPORTS\n\nD\n"
    )
    print(reorder_news_in_brief_last(sample))
