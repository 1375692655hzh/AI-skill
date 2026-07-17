#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Translate post texts to Simplified Chinese via configured LLM."""
from __future__ import annotations

import re
import sys
from typing import Any

from call_llm import call_llm


TRANSLATE_SYSTEM = (
    "你是一名专业的金融翻译。把用户给的社交媒体帖子翻译成简体中文。\n"
    "规则：\n"
    "1. 金融/市场术语保留英文原文或常用缩写，例如：BIST100、TUPRS、ASELS、IPO、Fed、"
    "ECB、CPI、PMI、EPS、PE、USD、TRY、TL。\n"
    "2. 股票代码（$TUPRS 等）原样保留。\n"
    "3. 保留 @handle、#话题、URL、emoji、换行结构。\n"
    "4. 只输出译文本身，不要加前缀、不要解释。"
)

PRESERVE_RE = re.compile(
    r"^(https?://\S+|@\w+$|\$[A-Z.]+$|\d+([\.,:]\d+)*%?$)$"
)


def _is_trivial(text: str) -> bool:
    if not text or not text.strip():
        return True
    return bool(PRESERVE_RE.match(text.strip()))


def translate_text(text: str, llm_cfg: dict, translate_cfg: dict) -> str:
    if not text or not text.strip():
        return ""
    if _is_trivial(text):
        return text.strip()
    try:
        return call_llm(
            prompt=text[:3000],
            provider=llm_cfg.get("provider", "minimax"),
            model=llm_cfg.get("model", "MiniMax-M3"),
            api_key_env=llm_cfg.get("api_key_env") or llm_cfg.get("api_key", "MINIMAX_API_KEY"),
            base_url=llm_cfg.get("base_url"),
            temperature=float(translate_cfg.get("temperature", 0.2)),
            max_tokens=int(translate_cfg.get("max_tokens", 2048)),
            system_message=TRANSLATE_SYSTEM,
            timeout=60,
        ).strip()
    except Exception as exc:
        return f"[翻译失败：{type(exc).__name__}: {exc}]"


def translate_posts(
    posts: list[dict[str, Any]],
    llm_cfg: dict,
    translate_cfg: dict,
) -> list[dict[str, Any]]:
    total = len(posts)
    for idx, post in enumerate(posts, 1):
        print(f"[{idx}/{total}] translate {post.get('account')} {post.get('id')}", file=sys.stderr)
        post["translation"] = translate_text(post.get("text") or "", llm_cfg, translate_cfg)
        q = post.get("quoted_text") or ""
        if q.strip():
            post["quoted_translation"] = translate_text(q, llm_cfg, translate_cfg)
        else:
            post["quoted_translation"] = ""
    return posts
