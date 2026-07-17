#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate Paraborsa all-in report output."""
from __future__ import annotations


def validate_summary(text: str) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if len(text) < 300:
        errors.append("Summary too short (< 300 chars).")
    if "【综合总结】" not in text and "综合总结" not in text:
        errors.append("Missing summary section header.")
    if "个股覆盖汇总" not in text and "| 标的 |" not in text:
        warnings.append("Summary may be missing ticker table.")
    if "券商观点速览" not in text:
        warnings.append("Summary may be missing broker quick view.")

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "length": len(text)}


def validate_report(text: str, *, min_articles: int = 1) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if len(text) < 500:
        errors.append("Output too short (< 500 chars).")
    if "【综合总结】" not in text:
        errors.append("Missing section: 【综合总结】")
    if "【拼接内容】" not in text:
        errors.append("Missing section: 【拼接内容】")
    if "个股覆盖汇总" not in text and "标的" not in text:
        warnings.append("Summary may be missing ticker coverage table.")
    if text.count("--- 第") < min_articles and "未抓到正文" not in text:
        warnings.append("Concat section may have fewer articles than expected.")

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "length": len(text)}


def validate(text: str, *, min_articles: int = 1) -> dict:
    return validate_report(text, min_articles=min_articles)
