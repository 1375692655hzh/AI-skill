#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate Info technical report format (table-focused)."""
from __future__ import annotations

import re

from sanitize_sources import validate_no_attribution


def _count_tables(text: str) -> int:
    return len(re.findall(r"(?m)^\|.+\|$", text))


def validate(text: str) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if len(text) < 500:
        errors.append("Output too short (< 500 chars).")
    if len(text) > 20000:
        warnings.append("Output longer than expected (> 20000 chars).")

    forbidden = [
        ("===", "separator ==="),
        ("━━━", "line separator"),
        ("**", "markdown bold"),
        ("__", "markdown italic"),
        ("🔴", "emoji"),
        ("🟢", "emoji"),
        ("⚠️", "emoji"),
    ]
    for marker, name in forbidden:
        if marker in text:
            errors.append(f"Found forbidden {name}: {marker}")

    table_count = _count_tables(text)
    if table_count < 4:
        errors.append(f"Too few markdown tables ({table_count}); need at least 4.")

    required_sections = [
        "核心观点",
        "BIST100 技术位",
        "超买",
        "成交",
        "重点个股技术位",
        "技术信号解读",
        "操作建议",
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
        "table_count": table_count,
        "attribution_hits": attribution.get("hits", []),
    }
