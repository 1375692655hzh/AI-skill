#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble the close-of-day LLM prompt without leaking source identities."""
from __future__ import annotations

from pathlib import Path

from sanitize_sources import sanitize_material, sanitize_prompt


def build_prompt(
    template_path: Path,
    today_date: str,
    target_date: str,
    weekday_cn: str,
    bloomberght_text: str,
    paraborsa_text: str,
    info_yatirim_text: str,
) -> str:
    template = template_path.read_text(encoding="utf-8")
    prompt = (
        template.replace("{today_date}", today_date)
        .replace("{target_date}", target_date)
        .replace("{weekday_cn}", weekday_cn)
        .replace("{closing_material}", sanitize_material(bloomberght_text) or "（无收盘数据）")
        .replace("{commentary_material}", sanitize_material(paraborsa_text) or "（无市场观点数据）")
        .replace("{technical_material}", sanitize_material(info_yatirim_text) or "（无技术/公告数据）")
    )
    return sanitize_prompt(prompt)
