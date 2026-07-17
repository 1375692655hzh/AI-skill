# -*- coding: utf-8 -*-
"""Unified UTF-8 JSON I/O. Avoids Windows GBK mishaps on json.dump/load."""
from __future__ import annotations

import json


def dump(obj, path, indent=1, ensure_ascii=False):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=ensure_ascii, indent=indent)


def load(path):
    """Try utf-8 first; fall back to common Taiwan encodings for legacy files."""
    for enc in ("utf-8", "utf-8-sig", "gbk", "cp950"):
        try:
            with open(path, encoding=enc) as f:
                return json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ValueError(f"cannot decode JSON: {path}")


def load_or_none(path):
    try:
        return load(path)
    except (OSError, ValueError):
        return None
