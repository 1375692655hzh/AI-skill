# -*- coding: utf-8 -*-
"""Resolve skill code root and shared data directory via env (set by generate_*.py)."""
from __future__ import annotations

import os


def code_root(fallback_file: str, *, up: int = 1) -> str:
    """
    Directory that contains collectors/ and lib/.
    Override with TAIWAN_EQUITY_ROOT (absolute path).
    """
    env = os.environ.get("TAIWAN_EQUITY_ROOT")
    if env:
        return os.path.abspath(env)
    p = os.path.abspath(fallback_file)
    for _ in range(up):
        p = os.path.dirname(p)
    return p


def data_dir(code_root_path=None):
    """
    Directory that holds YYYY-MM-DD subfolders (digest etc.).
    Override with TAIWAN_EQUITY_DATA (absolute path to that folder).
    """
    env = os.environ.get("TAIWAN_EQUITY_DATA")
    if env:
        return os.path.abspath(env)
    root = code_root_path or os.environ.get("TAIWAN_EQUITY_ROOT") or "."
    return os.path.join(os.path.abspath(root), "data")
