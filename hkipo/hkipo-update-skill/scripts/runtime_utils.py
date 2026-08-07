#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Portable path/stdio helpers for HK IPO skill — mirrors taiwan/runtime_utils.py."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Tuple


def configure_stdio() -> None:
    """Force UTF-8 stdout/stderr (Windows GBK mishaps on json output)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def resolve_skill_paths(
    config_path: Path,
    config: dict,
    *,
    default_data: str = "data",
    default_output: str = "output",
) -> Tuple[Path, Path, Path, Path, Path]:
    """Returns (skill_dir, workdir, data_dir, output_dir, db_path).

    All relative paths resolve against skill_dir (= config_path.parent).
    """
    config_path = config_path.resolve()
    skill_dir = config_path.parent

    def _resolve(key, default):
        p = Path(config.get(key, default)).expanduser()
        if not p.is_absolute():
            p = (skill_dir / p).resolve()
        return p.resolve()

    workdir = _resolve("workdir", ".")
    data_dir = _resolve("data_dir", default_data)
    output_dir = _resolve("output_dir", default_output)
    db_path = _resolve("db_path", str(Path(config.get("data_dir", default_data)) / "state.db"))

    for d in (data_dir, output_dir, db_path.parent):
        d.mkdir(parents=True, exist_ok=True)

    return skill_dir, workdir, data_dir, output_dir, db_path


def set_env(skill_dir, data_dir, output_dir):
    """Set HKIPO_ROOT / HKIPO_DATA / HKIPO_OUTPUT so submodules can resolve paths."""
    os.environ["HKIPO_ROOT"] = str(skill_dir)
    os.environ["HKIPO_DATA"] = str(data_dir)
    os.environ["HKIPO_OUTPUT"] = str(output_dir)
