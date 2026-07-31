#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate Info technical report format (table-focused)."""
from __future__ import annotations

import re

from sanitize_sources import validate_no_attribution


def _count_tables(text: str) -> int:
    return len(re.findall(r"(?m)^\|.+\|$", text))


def _extract_section(text: str, title: str) -> str:
    """Return body of 【title】 until next 【...】 or 风险提示."""
    pat = rf"【{re.escape(title)}】\s*(.*?)(?=\n【|\n风险提示|$)"
    m = re.search(pat, text, re.S)
    return (m.group(1) if m else "").strip()


def _extract_numbers(s: str) -> set[str]:
    """Fingerprint numeric tokens in source text for provenance check.

    Same logic as close/info_daily validators: percentages, prices with
    optional decimal, 亿里拉 amounts. Lookarounds (not \\b) so Chinese
    prefixes don't split numbers.
    """
    fps: set[str] = set()
    for m in re.finditer(r"-?[\d.,]+%", s):
        token = m.group(0).replace(",", ".").replace(" ", "")
        fps.add(token)
        fps.add(token.rstrip("%"))
        s = s[: m.start()] + " " * (m.end() - m.start()) + s[m.end() :]
    for m in re.finditer(r"[\d.]+亿里拉", s):
        full = m.group(0)
        fps.add(full)
        fps.add(full.replace("亿里拉", ""))
        s = s[: m.start()] + " " * (m.end() - m.start()) + s[m.end() :]
    for m in re.finditer(r"(?<![\d.])\d{1,5}(?:[.,]\d{1,4})?(?![\d.])", s):
        fps.add(m.group(0).replace(",", "."))
    return fps


def _strip_unit_suffix(fp: str) -> str:
    """Strip Chinese unit suffixes so '179.4亿里拉' matches source '179.4'."""
    for suffix in ("亿里拉", "亿拉", "里拉", "亿"):
        if fp.endswith(suffix):
            return fp[: -len(suffix)]
    return fp


def _num_core(fp: str) -> str | None:
    """Normalize numeric token for float-equivalence (13458.10 ↔ 13458.1)."""
    bare = _strip_unit_suffix(fp).rstrip("%")
    if bare.startswith("-"):
        bare = bare[1:]
    if not re.fullmatch(r"\d+(?:\.\d+)?", bare):
        return None
    try:
        return f"{float(bare):.10g}"
    except ValueError:
        return None


def _fp_in_source(fp: str, src_fps: set[str]) -> bool:
    """Check fingerprint with sign/unit/%/trailing-zero tolerance."""
    if fp in src_fps:
        return True
    variants = {fp}
    for v in list(variants):
        if v.startswith("-"):
            variants.add(v[1:])
    for v in list(variants):
        bare = v.rstrip("%")
        if bare != v:
            variants.add(bare)
    for v in list(variants):
        stripped = _strip_unit_suffix(v)
        if stripped != v:
            variants.add(stripped)
    for v in list(variants):
        if v.startswith("-"):
            variants.add(v[1:])
        bare = v.rstrip("%")
        if bare != v:
            variants.add(bare)
    if any(v in src_fps for v in variants):
        return True
    core = _num_core(fp)
    if core is None:
        return False
    for s in src_fps:
        sc = _num_core(s)
        if sc is not None and sc == core:
            return True
    return False


def validate(text: str, *, source_facts: str | None = None) -> dict:
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

    # Data-provenance check on the BIST100 technical table only.
    # The full report has 30+ stocks × 8 levels each — too dense to verify
    # every cell without false positives. The BIST100 table is the headline
    # number and the most likely place for an LLM to misremember; check it
    # as a WARNING (tables are LLM-filled and may legitimately round).
    if source_facts:
        src_fps = _extract_numbers(source_facts)
        extra = set()
        for fp in list(src_fps):
            extra.add(fp.replace(",", ""))
            extra.add(fp.replace(".", ""))
        src_fps |= extra
        ignore = {str(y) for y in range(2020, 2031)} | {"1", "2", "3", "100"}
        bist = _extract_section(text, "BIST100 技术位")
        if bist:
            out_fps = _extract_numbers(bist) - ignore
            suspicious = []
            for fp in sorted(out_fps):
                if _fp_in_source(fp, src_fps):
                    continue
                suspicious.append(fp)
            if suspicious:
                warnings.append(
                    f"[BIST100 技术位] numbers not found in Info bulletin: {suspicious[:8]}. "
                    "Verify against source; table cells may be rounded but should not be invented."
                )

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
