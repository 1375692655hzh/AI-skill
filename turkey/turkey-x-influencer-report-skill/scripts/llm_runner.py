#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM generation with optional validation retry."""
from __future__ import annotations

from typing import Callable

from call_llm import call_llm


def generate_with_validation(
    prompt: str,
    llm_cfg: dict,
    validate_fn: Callable[[str], dict],
    *,
    system_message: str = "You are a Turkish market analyst writing Chinese investment notes.",
) -> tuple[str | None, dict]:
    api_key_env = llm_cfg.get("api_key") or llm_cfg.get("api_key_env", "OPENAI_API_KEY")
    provider = llm_cfg.get("provider", "openai")
    model = llm_cfg.get("model", "gpt-4o")
    base_url = llm_cfg.get("base_url")
    temperature = llm_cfg.get("temperature", 0.3)
    max_tokens = llm_cfg.get("max_tokens", 8000)

    try:
        output = call_llm(
            prompt=prompt,
            provider=provider,
            model=model,
            api_key_env=api_key_env,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            system_message=system_message,
        )
    except Exception as exc:
        return None, {"ok": False, "errors": [str(exc)], "warnings": []}

    validation = validate_fn(output)
    if not validation.get("ok"):
        fix_prompt = (
            prompt
            + "\n\n【重要修订】上一版格式不合格："
            + "; ".join(validation.get("errors", [])[:5])
            + "。请按模板用【】标题完整重写。"
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
                system_message=system_message,
            )
            validation = validate_fn(output)
        except Exception as exc:
            return None, {"ok": False, "errors": [str(exc)], "warnings": []}

    return output, validation
