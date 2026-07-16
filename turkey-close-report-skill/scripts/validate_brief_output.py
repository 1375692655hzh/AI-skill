#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate structured close-report brief output."""
from __future__ import annotations

import re

from sanitize_sources import validate_no_attribution


REQUIRED_FIELDS = (
    "【指数】",
    "【汇率】",
    "【驱动】",
    "【个股】",
    "【板块】",
    "【信号】",
    "【操作】",
    "【风险】",
)

_STOCK_LINE_RE = re.compile(r"^[A-Z][A-Z0-9]{2,7}\s+\S")
# 汉字 + 中文标点（全角符号、中文标点区）；不含英文 ticker / 数字 / 空白
_CN_CHAR_RE = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]")


def count_cn_chars(text: str) -> int:
    """Count Chinese characters + Chinese/fullwidth punctuation only."""
    return len(_CN_CHAR_RE.findall(text or ""))


def _validate_stock_section(text: str, errors: list[str]) -> None:
    match = re.search(r"【个股】\s*\n((?:.+\n)+?)(?=【板块】)", text)
    if not match:
        errors.append("【个股】 section must be a header line followed by one stock per line.")
        return
    stock_lines = [line.strip() for line in match.group(1).splitlines() if line.strip()]
    if len(stock_lines) < 3:
        errors.append("【个股】 section needs at least 3 stocks, one per line.")
    if len(stock_lines) > 6:
        errors.append("【个股】 section has too many stock lines (> 6).")
    for line in stock_lines:
        if not _STOCK_LINE_RE.match(line):
            errors.append(f"Invalid stock line format: {line[:40]}")


def validate_brief(
    text: str,
    *,
    min_chars: int = 400,
    max_chars: int = 500,
) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    length = count_cn_chars(text)

    if length < min_chars:
        errors.append(f"Brief too short (< {min_chars} Chinese chars).")
    if length > max_chars:
        errors.append(f"Brief too long (> {max_chars} Chinese chars).")

    if "简报" not in text:
        errors.append("Missing brief title marker (简报).")

    for marker, name in [
        ("===", "separator ==="),
        ("---", "separator ---"),
        ("**", "markdown bold"),
        ("🔴", "emoji"),
    ]:
        if marker in text:
            errors.append(f"Found forbidden {name}: {marker}")

    if re.search(r"(?m)^\s*[-•*]\s", text):
        errors.append("Found list bullet at line start.")

    for field in REQUIRED_FIELDS:
        if field not in text:
            errors.append(f"Missing field: {field}")

    _validate_stock_section(text, errors)

    attribution = validate_no_attribution(text)
    errors.extend(attribution["errors"])

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "length": length,
        "attribution_hits": attribution.get("hits", []),
    }
