#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the condensed close-report prompt from a validated full report."""
from __future__ import annotations

from pathlib import Path

from sanitize_sources import sanitize_prompt


def build_brief_prompt(
    template_path: Path,
    today_date: str,
    weekday_cn: str,
    full_report: str,
) -> str:
    template = template_path.read_text(encoding="utf-8")
    prompt = (
        template.replace("{today_date}", today_date)
        .replace("{weekday_cn}", weekday_cn)
        .replace("{full_report}", full_report.strip())
    )
    return sanitize_prompt(prompt)
