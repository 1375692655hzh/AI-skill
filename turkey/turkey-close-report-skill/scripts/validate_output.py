#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate close-of-day report format and forbid source attribution."""
from __future__ import annotations

import re

from sanitize_sources import validate_no_attribution


FACT_SECTIONS = (
    "大盘概况",
    "关键个股异动",
    "行业板块表现",
    "汇市与大宗商品",
)

# Structured concise slots (not char-count caps); each slot must start its own line
STRUCTURED_SECTIONS = {
    "核心信号与逻辑": ("驱动：", "技术：", "资金情绪："),
    "后市策略参考": ("仓位：", "点位：", "回避："),
}

# Soft ban: analysis / causal language inside the four BHT-only fact sections
FACT_ANALYSIS_PATTERNS = [
    r"由于",
    r"因为",
    r"导致",
    r"受到?.*?(压制|推动|拖累|提振)",
    r"市场认为",
    r"暗示",
    r"预计",
    r"展望",
    r"支撑位",
    r"阻力位",
    r"均线",
    r"RSI",
    r"MACD",
    r"情绪面",
    r"资金面",
    r"技术面",
]


def _extract_section(text: str, title: str) -> str:
    """Return body of 【title】 until next 【...】 or 风险提示."""
    pat = rf"【{re.escape(title)}】\s*(.*?)(?=\n【|\n风险提示|$)"
    m = re.search(pat, text, re.S)
    return (m.group(1) if m else "").strip()


def _count_sentences(body: str) -> int:
    parts = [p.strip() for p in re.split(r"[。！？]", body) if p.strip()]
    return len(parts)


def _slot_on_own_line(body: str, slot: str) -> bool:
    """True if some non-empty line starts with the slot label."""
    for line in body.splitlines():
        if line.strip().startswith(slot):
            return True
    return False


def _slots_are_consecutive_lines(body: str, slots: tuple[str, ...]) -> bool:
    """Slots should be on consecutive lines (换行), not separated by blank lines."""
    lines = [ln.strip() for ln in body.splitlines()]
    idxs: list[int] = []
    for i, line in enumerate(lines):
        if any(line.startswith(slot) for slot in slots):
            idxs.append(i)
    if len(idxs) < 2:
        return True
    for a, b in zip(idxs, idxs[1:]):
        if b != a + 1:
            return False
    return True


def validate(text: str) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

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

    if re.search(r"(?m)^\s*[-•*]\s", text):
        errors.append("Found list bullet at line start.")
    if re.search(r"(?m)^\s*\d+[.)]\s", text):
        errors.append("Found numbered list.")

    # Hard ban: clock stamps (esp. BHT 18:30) anywhere in finished report
    if re.search(r"\b18:30\b", text) or "18：30" in text:
        errors.append("Found forbidden clock stamp 18:30 (FX/commodities must not include time).")
    if re.search(r"\d{1,2}:\d{2}", text):
        # Allow ISO dates like 2026-07-27 only; ban HH:MM
        if re.search(r"(?<!\d{4}-\d{2}-\d{2}T)\b\d{1,2}:\d{2}\b", text):
            errors.append("Found clock time HH:MM; remove time stamps from FX/commodities and body.")

    required_sections = [
        "核心结论",
        "大盘概况",
        "关键个股异动",
        "行业板块表现",
        "汇市与大宗商品",
        "核心信号与逻辑",
        "后市策略参考",
    ]
    for section in required_sections:
        if section not in text:
            errors.append(f"Missing section: {section}")

    if "风险提示" not in text and "不构成投资建议" not in text:
        warnings.append("Risk warning or disclaimer missing.")

    # Fact sections: prefer 亿里拉; flag analysis tone
    for title in FACT_SECTIONS:
        body = _extract_section(text, title)
        if not body:
            continue
        if re.search(r"\d{1,3}(?:\.\d{3}){2,}\s*(?:TL|里拉)", body):
            warnings.append(
                f"[{title}] large TL amount looks unconverted; prefer 「亿里拉」."
            )
        for ap in FACT_ANALYSIS_PATTERNS:
            if re.search(ap, body):
                warnings.append(f"[{title}] looks analytical (matched /{ap}/); keep BHT facts only.")
                break

    # 关键个股异动: prefer 涨跌幅 on a new line after 成交额
    stocks = _extract_section(text, "关键个股异动")
    if stocks and "成交" in stocks and ("涨幅" in stocks or "跌幅" in stocks):
        # ok if blank line OR just next line; fail only if same line
        if re.search(r"成交[^\n]*涨幅|成交[^\n]*跌幅", stocks):
            warnings.append("[关键个股异动] 成交额与涨跌幅应换行分行，不要挤同一行.")

    # Opinion sections: require slot labels each on its own line
    for title, slots in STRUCTURED_SECTIONS.items():
        body = _extract_section(text, title)
        if not body:
            continue
        missing = [s for s in slots if s not in body]
        if missing:
            errors.append(f"[{title}] missing structured slots: {', '.join(missing)}")
        not_lined = [s for s in slots if s in body and not _slot_on_own_line(body, s)]
        if not_lined:
            errors.append(
                f"[{title}] slots must each start a new line: {', '.join(not_lined)}"
            )
        if not missing and not not_lined and not _slots_are_consecutive_lines(body, slots):
            errors.append(
                f"[{title}] slots must be consecutive lines (换行分行，不要空行)."
            )
        n_sent = _count_sentences(body)
        # 3 slots ≈ 3 sentences; allow slight overflow, reject long essays
        if n_sent > 6:
            errors.append(
                f"[{title}] too many sentences ({n_sent} > 6); keep one sentence per slot."
            )
        elif n_sent < 3:
            warnings.append(f"[{title}] fewer than 3 sentences; each slot should be one sentence.")

    attribution = validate_no_attribution(text)
    errors.extend(attribution["errors"])

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "length": len(text),
        "attribution_hits": attribution.get("hits", []),
    }
