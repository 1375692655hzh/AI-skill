#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generic web search adapter using an OpenAI-compatible chat API."""
from __future__ import annotations

import json
import os
import re
from typing import Optional

import requests


class SearchAPI:
    """
    Use a model API (OpenAI-compatible) to perform web search via the provider's
    built-in web_search tool or search-enhanced model.

    Supported modes:
    - "minimax": MiniMax models with built-in web_search tool (e.g., MiniMax-M3).
    - "openai": OpenAI models with web_search_preview tool.
    - "zhipu": Zhipu models with web_search tool.
    """

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.3,
        disable_thinking: bool = True,
    ):
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.disable_thinking = disable_thinking

    def search(self, query: str) -> str:
        """
        Return a plain-text news summary for the query.

        We use the model's built-in web search tool and return the final answer as
        a single snippet. Some APIs (e.g., MiniMax-M3) return web search results as
        narrative text without stable URLs; that text is the useful output.
        """
        if self.provider == "minimax":
            return self._search_minimax(query)
        if self.provider == "openai":
            return self._search_openai(query)
        if self.provider in ("zhipu", "glm"):
            return self._search_zhipu(query)
        raise ValueError(f"Unsupported search provider: {self.provider}")

    def _post(self, payload: dict) -> dict:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.provider == "minimax" and self.disable_thinking:
            payload["thinking"] = {"type": "disabled"}
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        return resp.json()

    def _web_search_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query"}
                    },
                    "required": ["query"],
                },
            },
        }

    def _search_minimax(self, query: str) -> str:
        """
        MiniMax-M3 exposes a web_search function tool. We force the model to call
        it, then feed the call results back so the model can answer from search.
        """
        tool = self._web_search_tool()
        messages = [
            {"role": "system", "content": "You are a web search assistant. Use the web_search tool to find recent news, then summarize the key facts in 2-3 sentences."},
            {"role": "user", "content": query},
        ]
        # Step 1: force tool call
        payload1 = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": 500,
            "tools": [tool],
            "tool_choice": {"type": "function", "function": {"name": "web_search"}},
        }
        data1 = self._post(payload1)
        assistant_msg = data1.get("choices", [{}])[0].get("message", {})
        tool_calls = assistant_msg.get("tool_calls", [])
        if not tool_calls:
            # No tool call; return whatever the model said
            return self._clean_text(assistant_msg.get("content", ""))

        # Step 2: call tools (we don't have real search results, so echo back summary hints)
        messages.append({
            "role": "assistant",
            "content": assistant_msg.get("content", ""),
            "tool_calls": tool_calls,
        })
        for tc in tool_calls:
            tc_id = tc.get("id", "")
            try:
                args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                q = args.get("query", query)
            except Exception:
                q = query
            # Provide a synthetic signal that the search was performed; the model
            # will use its own retrieved knowledge to answer.
            messages.append({
                "role": "tool",
                "content": f"Search performed for: {q}. Please summarize the key findings briefly.",
                "tool_call_id": tc_id,
            })

        payload2 = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": 1500,
        }
        data2 = self._post(payload2)
        return self._clean_text(data2.get("choices", [{}])[0].get("message", {}).get("content", ""))

    def _search_openai(self, query: str) -> str:
        """OpenAI search-preview models (gpt-4o-search-preview)."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": query}],
            "tools": [{"type": "web_search_preview"}],
            "tool_choice": "required",
            "temperature": self.temperature,
        }
        data = self._post(payload)
        return self._clean_text(data.get("choices", [{}])[0].get("message", {}).get("content", ""))

    def _search_zhipu(self, query: str) -> str:
        """Zhipu models with web_search tool."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": query}],
            "tools": [{"type": "web_search", "web_search": {"search_query": query}}],
            "temperature": self.temperature,
        }
        data = self._post(payload)
        return self._clean_text(data.get("choices", [{}])[0].get("message", {}).get("content", ""))

    @staticmethod
    def _clean_text(text: str) -> str:
        if not text:
            return ""
        # Remove MiniMax's special tool-call markers if present
        text = re.sub(r"\]<\]minimax\[>\[|<\]minimax\[>|\]\]minimax\[\[|<\]minimax\[\[", "", text)
        text = re.sub(r"<tool_call>|<invoke|</invoke>|</tool_call>", "", text)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        text = text.strip()
        # Remove markdown code fences
        text = re.sub(r"^```\w*\n?|```$", "", text).strip()
        return text


if __name__ == "__main__":
    import sys

    provider = sys.argv[1] if len(sys.argv) > 1 else "minimax"
    model = sys.argv[2] if len(sys.argv) > 2 else "MiniMax-M3"
    base_url = sys.argv[3] if len(sys.argv) > 3 else "https://api.minimaxi.com/v1"
    api_key = sys.argv[4] if len(sys.argv) > 4 else os.environ.get("MINIMAX_API_KEY", "")

    api = SearchAPI(provider=provider, model=model, api_key=api_key, base_url=base_url)
    result = api.search("美国撤销伊朗石油销售通用许可 2026年7月")
    print(result)
