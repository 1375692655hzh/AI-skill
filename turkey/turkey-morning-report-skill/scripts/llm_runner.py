#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared LLM generation with validation and attribution retry."""
from __future__ import annotations

from typing import Callable

from call_llm import call_llm


def generate_with_validation(
    prompt: str,
    llm_cfg: dict,
    validate_fn: Callable[[str], dict],
    *,
    fix_attribution: bool = True,
) -> tuple[str | None, dict]:
    api_key_env = llm_cfg.get("api_key") or llm_cfg.get("api_key_env", "OPENAI_API_KEY")
    provider = llm_cfg.get("provider", "openai")
    model = llm_cfg.get("model", "gpt-4o")
    base_url = llm_cfg.get("base_url")
    temperature = llm_cfg.get("temperature", 0.4)
    max_tokens = llm_cfg.get("max_tokens", 2500)

    try:
        output = call_llm(
            prompt=prompt,
            provider=provider,
            model=model,
            api_key_env=api_key_env,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        return None, {"ok": False, "errors": [str(exc)], "warnings": []}

    validation = validate_fn(output)
    if not validation["ok"] and fix_attribution and validation.get("attribution_hits"):
        fix_prompt = (
            prompt
            + "\n\n【重要修订】你上一版草稿仍出现了来源署名。"
            "请完全重写：正文不得出现任何机构/平台/网站/报告名称。"
        )
        try:
            output = call_llm(
                prompt=fix_prompt,
                provider=provider,
                model=model,
                api_key_env=api_key_env,
                base_url=base_url,
                temperature=max(0.2, temperature - 0.1),
                max_tokens=max_tokens,
            )
            validation = validate_fn(output)
        except Exception as exc:
            return None, {"ok": False, "errors": [str(exc)], "warnings": []}

    length_errors = [e for e in validation.get("errors", []) if "too short" in e or "too long" in e]
    structure_errors = [
        e
        for e in validation.get("errors", [])
        if "structured slots" in e
        or "too many sentences" in e
        or "start a new line" in e
        or "consecutive lines" in e
        or "国际新闻" in e
    ]
    if not validation["ok"] and (length_errors or structure_errors):
        fix_prompt = (
            prompt
            + "\n\n【重要修订】你上一版草稿结构/字数不合格："
            + "；".join(structure_errors + length_errors)
            + "。请重写整篇："
            "【关键个股】【行业板块表现】只复述BHT事实卡；【汇市与大宗商品】只复述最新报价事实；"
            "【国际新闻】只复述国际新闻素材卡，每条新闻独占一行共2–3行；"
            "【今日操作参考】写成三行：仓位：……。\\n点位：……。\\n回避：……。；"
            "只要换行不要空行；其余格式铁律不变。"
        )
        try:
            output = call_llm(
                prompt=fix_prompt,
                provider=provider,
                model=model,
                api_key_env=api_key_env,
                base_url=base_url,
                temperature=max(0.2, temperature - 0.05),
                max_tokens=max_tokens,
            )
            validation = validate_fn(output)
        except Exception as exc:
            return None, {"ok": False, "errors": [str(exc)], "warnings": []}

    return output, validation
