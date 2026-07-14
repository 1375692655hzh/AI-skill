#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate the close report output against format rules."""
from __future__ import annotations

import re


def validate(text: str) -> dict:
    errors = []
    warnings = []

    if len(text) < 300:
        errors.append("Output too short (< 300 chars).")
    if len(text) > 6000:
        warnings.append("Output longer than expected (> 6000 chars).")

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

    # Check bullet/list markers at line start
    if re.search(r"(?m)^\s*[-•*]\s", text):
        errors.append("Found list bullet at line start.")
    if re.search(r"(?m)^\s*\d+[.)]\s", text):
        errors.append("Found numbered list.")

    # Required sections
    required_sections = ["核心结论", "大盘概况", "关键个股异动", "行业板块表现", "汇市与大宗商品", "核心信号与逻辑", "后市策略参考"]
    for section in required_sections:
        if section not in text:
            errors.append(f"Missing section: {section}")

    # Risk warning
    if "风险提示" not in text and "不构成投资建议" not in text:
        warnings.append("Risk warning or disclaimer missing.")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "length": len(text),
    }


if __name__ == "__main__":
    import sys
    from pathlib import Path

    text = Path(sys.argv[1]).read_text(encoding="utf-8") if len(sys.argv) > 1 else sys.stdin.read()
    r = validate(text)
    import json
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r["ok"] else 1)
