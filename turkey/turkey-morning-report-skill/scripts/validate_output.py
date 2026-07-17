#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate morning-briefing output format and forbid source attribution."""
from __future__ import annotations

import re

from sanitize_sources import validate_no_attribution


def validate(text: str) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if len(text) < 300:
        errors.append("Output too short (< 300 chars).")
    if len(text) > 5000:
        warnings.append("Output longer than expected (> 5000 chars).")

    forbidden = [
        ("===", "separator ==="),
        ("---", "separator ---"),
        ("━━━", "line separator"),
        ("**", "markdown bold"),
        ("__", "markdown italic"),
        ("🔴", "emoji"),
        ("🟢", "emoji"),
        ("⚠️", "emoji"),
        ("❌", "emoji"),
        ("✅", "emoji"),
    ]
    for marker, name in forbidden:
        if marker in text:
            errors.append(f"Found forbidden {name}: {marker}")

    if re.search(r"(?m)^\s*[-•*]\s", text):
        errors.append("Found list bullet at line start.")
    if re.search(r"(?m)^\s*\d+[.)]\s", text):
        errors.append("Found numbered list.")

    required_sections = [
        "核心观点",
        "国际新闻",
        "关键个股",
        "行业板块表现",
        "汇市与大宗商品",
        "今日操作参考",
    ]
    for section in required_sections:
        if section not in text:
            errors.append(f"Missing section: {section}")

    if "风险提示" not in text and "不构成投资建议" not in text:
        warnings.append("Risk warning or disclaimer missing.")

    attribution = validate_no_attribution(text)
    errors.extend(attribution["errors"])

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "length": len(text),
        "attribution_hits": attribution.get("hits", []),
    }
