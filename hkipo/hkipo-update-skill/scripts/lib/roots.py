# -*- coding: utf-8 -*-
"""Resolve skill code root and data directory via env (set by run_*.py).

Mirrors taiwan-afterhours-skill/lib/roots.py; uses HKIPO_ROOT / HKIPO_DATA envs.
"""
from __future__ import annotations

import os


def code_root(fallback_file: str, *, up: int = 1) -> str:
    """Directory that contains collectors/ and lib/. Override with HKIPO_ROOT."""
    env = os.environ.get("HKIPO_ROOT")
    if env:
        return os.path.abspath(env)
    p = os.path.abspath(fallback_file)
    for _ in range(up):
        p = os.path.dirname(p)
    return p


def data_dir(code_root_path=None) -> str:
    """Directory that holds state.db, archive/, and YYYY-MM-DD snapshots."""
    env = os.environ.get("HKIPO_DATA")
    if env:
        return os.path.abspath(env)
    root = code_root_path or os.environ.get("HKIPO_ROOT") or "."
    return os.path.join(os.path.abspath(root), "data")


def output_dir(code_root_path=None) -> str:
    """Directory that holds daily_digest.md and pushed_notifications.log."""
    env = os.environ.get("HKIPO_OUTPUT")
    if env:
        return os.path.abspath(env)
    root = code_root_path or os.environ.get("HKIPO_ROOT") or "."
    return os.path.join(os.path.abspath(root), "output")
