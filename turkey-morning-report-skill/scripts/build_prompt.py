#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble the morning-briefing LLM prompt without leaking source identities."""
from __future__ import annotations

from pathlib import Path

from sanitize_sources import sanitize_material, sanitize_prompt


def build_prompt(
    template_path: Path,
    today_date: str,
    target_date: str,
    closing_text: str,
    news_text: str,
) -> str:
    template = template_path.read_text(encoding="utf-8")
    prompt = (
        template.replace("{today_date}", today_date)
        .replace("{target_date}", target_date)
        .replace("{closing_material}", sanitize_material(closing_text) or "（无收盘数据）")
        .replace("{news_material}", sanitize_material(news_text) or "（无补充新闻数据）")
    )
    return sanitize_prompt(prompt)
