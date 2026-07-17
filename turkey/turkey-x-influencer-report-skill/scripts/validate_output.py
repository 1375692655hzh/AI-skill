#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate full / curated report outputs."""
from __future__ import annotations

from typing import Any


def validate_full_report(text: str) -> dict[str, Any]:
    errors = []
    warnings = []
    if not text or not text.strip():
        return {"ok": False, "errors": ["empty full report"], "warnings": []}
    if "【推特大V全文" not in text and "【原文】" not in text:
        errors.append("missing full-report header or 【原文】 markers")
    if "【原文】" in text and "【译文】" not in text:
        warnings.append("has 【原文】 but no 【译文】")
    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}


def validate_curated_report(text: str) -> dict[str, Any]:
    errors = []
    warnings = []
    if not text or not text.strip():
        return {"ok": False, "errors": ["empty curated report"], "warnings": []}
    required = ["【推特大V精选", "【精选热点】", "【背景说明】", "【投资分析】"]
    for marker in required:
        if marker not in text:
            errors.append(f"missing section {marker}")
    if "【风险提示】" not in text:
        warnings.append("missing 【风险提示】")
    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}
