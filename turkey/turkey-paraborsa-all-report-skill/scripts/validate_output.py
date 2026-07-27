#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate Paraborsa all-in report output."""
from __future__ import annotations

import re


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
        errors.append("Missing section: 券商观点速览")
    else:
        for slot in ("技术位共识：", "宏观与事件：", "资金与标的："):
            if slot not in text:
                errors.append(f"[券商观点速览] missing structured slot: {slot}")
        # Reject old per-broker wall (many "Name：" lines after 速览)
        m = re.search(r"券商观点速览\s*(.*?)(?=\n分歧点|\n【|$)", text, re.S)
        body = (m.group(1) if m else "").strip()
        brokerish = re.findall(
            r"(?m)^(?:A1 Capital|Ahlatcı|Alnus|Anadolu|Bizim|Bulls|Deniz|Destek|"
            r"Garanti|Gedik|Global|ICBC|İnfo|Info|İntegral|Integral|Meksa|NCM|"
            r"Oyak|Phillip|Şeker|Sentiment|Tacirler|Vakıf|Ziraat)[^:\n]{0,20}：",
            body,
        )
        if len(brokerish) >= 5:
            errors.append(
                "[券商观点速览] looks like per-broker wall; synthesize into "
                "技术位共识/宏观与事件/资金与标的 only."
            )

    if "分歧点" not in text:
        warnings.append("Summary may be missing 分歧点.")

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

    # Re-check summary synthesis rules on the full report
    sub = validate_summary(text)
    for e in sub["errors"]:
        if e not in errors and "Summary too short" not in e and "summary section header" not in e:
            errors.append(e)
    warnings.extend([w for w in sub["warnings"] if w not in warnings])

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "length": len(text)}


def validate(text: str, *, min_articles: int = 1) -> dict:
    return validate_report(text, min_articles=min_articles)
