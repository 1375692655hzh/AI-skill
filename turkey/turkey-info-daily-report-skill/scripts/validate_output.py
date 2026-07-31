#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate Info daily report format (text-focused, no tables)."""
from __future__ import annotations

import re

from sanitize_sources import validate_no_attribution


# Sections that primarily report hard numbers copied from the Info bulletin.
# Numbers in these sections must appear in the source fingerprint so the LLM
# cannot fabricate prices/percentages. Analytical sections (今日展望, 操作建议)
# are exempt because they legitimately discuss round-number support/resistance
# levels and position sizing that are not in the source.
NUMERIC_FACT_SECTIONS = (
    "昨日收盘回顾",
    "关键数据",
)


def _extract_section(text: str, title: str) -> str:
    """Return body of 【title】 until next 【...】 or 风险提示."""
    pat = rf"【{re.escape(title)}】\s*(.*?)(?=\n【|\n风险提示|$)"
    m = re.search(pat, text, re.S)
    return (m.group(1) if m else "").strip()


def _extract_numbers(s: str) -> set[str]:
    """Fingerprint numeric tokens in source text for provenance check.

    Captures percentages, index closes / FX / commodity prices with optional
    decimal, and 亿里拉 amounts. Uses lookarounds (not \\b) so Chinese
    prefixes don't split the number — see close/validate_output.py for the
    full rationale of why \\b fails in re.UNICODE mode on Chinese text.
    """
    fps: set[str] = set()
    # Percentages first (greedy, optional leading -): -2.48% / 1.26%
    # Record BOTH the full "-2.48%" and the bare "-2.48" so an output that
    # writes the number without the trailing % still matches the source.
    for m in re.finditer(r"-?[\d.,]+%", s):
        token = m.group(0).replace(",", ".").replace(" ", "")
        fps.add(token)
        fps.add(token.rstrip("%"))
        s = s[: m.start()] + " " * (m.end() - m.start()) + s[m.end() :]
    # 亿里拉 amounts: 179.41亿里拉 — record full + bare numeric
    for m in re.finditer(r"[\d.]+亿里拉", s):
        full = m.group(0)
        fps.add(full)
        fps.add(full.replace("亿里拉", ""))
        s = s[: m.start()] + " " * (m.end() - m.start()) + s[m.end() :]
    # Prices / closes with optional decimal: 13515.54 / 47.40 / 4016 / 63996.
    # Allow 1-digit integer part (e.g. 0,57 / 9,40) — Info bulletins store
    # percentage-like table cells as bare "0,57" without a % sign, since the
    # unit is conveyed by the column header. Without this, a leading "0," or
    # single-digit "9," would be skipped and then flagged as fabricated.
    # Consume the whole numeric run so "47.40" is one token, not "47" + "40".
    # Lookarounds (not \b) so Chinese prefixes don't split the number.
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
    """Check if a fingerprint token appears in source with sign/unit/%/tail-zero tolerance.

    The LLM may legitimately add a leading '-' (source table column implies
    direction), append '%' (source conveys it via header), convert units
    (Milyon TL → 亿里拉), or drop trailing zeros (13458.10 → 13458.1).
    """
    if fp in src_fps:
        return True
    # Enumerate the cartesian product of {strip '-', keep '-'} × {strip '%', keep '%'}
    # × {strip unit suffix, keep suffix}. 8 variants max — cheap and complete.
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
    # Need a second sweep: stripping the unit suffix may expose a new strip-able
    # '%' or '-' (e.g. 'X亿里拉%' has no suffix exposed until we look again).
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

    if len(text) < 400:
        errors.append("Output too short (< 400 chars).")
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
    ]
    for marker, name in forbidden:
        if marker in text:
            errors.append(f"Found forbidden {name}: {marker}")

    if re.search(r"(?m)^\s*[-•*]\s", text):
        errors.append("Found list bullet at line start.")
    if re.search(r"(?m)^\s*\d+[.)]\s", text):
        errors.append("Found numbered list.")
    if re.search(r"\|.+\|", text):
        errors.append("Found markdown table; daily report must be prose only.")

    required_sections = [
        "核心观点",
        "隔夜要闻",
        "昨日收盘回顾",
        "今日展望",
        "关键数据",
        "操作建议",
    ]
    for section in required_sections:
        if section not in text:
            errors.append(f"Missing section: {section}")

    if "风险提示" not in text and "不构成投资建议" not in text:
        warnings.append("Risk warning or disclaimer missing.")

    # Data-provenance check: numbers in fact sections should appear in the Info
    # bulletin fingerprint. WARNING level — Info bulletins are raw Turkish text
    # where the LLM must legitimately convert units (Milyon TL → 亿里拉) and
    # reformat numbers (Turkish "17.940,9" → Chinese "179.4"). A hard error
    # here would flag these legal conversions as fabrication. We keep the
    # check as a warning so genuine hallucinations are surfaced for review
    # without blocking delivery.
    if source_facts:
        src_fps = _extract_numbers(source_facts)
        # Tolerate formatting differences: also store comma/dot-stripped forms.
        extra = set()
        for fp in list(src_fps):
            extra.add(fp.replace(",", ""))
            extra.add(fp.replace(".", ""))
        src_fps |= extra
        # Common non-data numbers to ignore: years, small ordinals, BIST100's "100"
        ignore = {str(y) for y in range(2020, 2031)} | {"1", "2", "3", "4", "5", "100"}
        for title in NUMERIC_FACT_SECTIONS:
            body = _extract_section(text, title)
            if not body:
                continue
            out_fps = _extract_numbers(body) - ignore
            # Match in either direction with unit/sign transparency:
            # - "%" is optional on either side (source tables convey it via header)
            # - leading "-" is optional (LLM may add sign to a bare magnitude)
            # - unit suffixes like 亿里拉/亿拉 are stripped before matching
            suspicious = []
            for fp in sorted(out_fps):
                if _fp_in_source(fp, src_fps):
                    continue
                suspicious.append(fp)
            if suspicious:
                warnings.append(
                    f"[{title}] numbers not found verbatim in Info bulletin: {suspicious[:8]}. "
                    "May be a legal unit conversion (Milyon TL→亿里拉) or rounding; "
                    "verify against source if any look fabricated."
                )

    attribution = validate_no_attribution(text)
    errors.extend(attribution["errors"])

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "length": len(text),
        "attribution_hits": attribution.get("hits", []),
    }
