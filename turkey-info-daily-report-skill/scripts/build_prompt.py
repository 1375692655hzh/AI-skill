#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble the Info daily bulletin LLM prompt."""
from __future__ import annotations

from pathlib import Path

from sanitize_sources import sanitize_material, sanitize_prompt


def build_prompt(
    template_path: Path,
    target_date: str,
    weekday_cn: str,
    bulletin_text: str,
) -> str:
    template = template_path.read_text(encoding="utf-8")
    prompt = (
        template.replace("{target_date}", target_date)
        .replace("{weekday_cn}", weekday_cn)
        .replace("{bulletin_material}", sanitize_material(bulletin_text) or "（无公告数据）")
    )
    return sanitize_prompt(prompt)
