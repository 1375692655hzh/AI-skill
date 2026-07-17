#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Portable path helpers for Taiwan equity skills."""
from __future__ import annotations

import sys
from pathlib import Path


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def resolve_skill_paths(config_path: Path, config: dict, *, default_data: str = "data", default_output: str = "output"):
    """
    Returns (skill_dir, workdir, data_dir, output_dir).
    data_dir is the folder that contains YYYY-MM-DD subdirs.
    """
    config_path = config_path.resolve()
    skill_dir = config_path.parent

    workdir = Path(config.get("workdir", ".")).expanduser()
    if not workdir.is_absolute():
        workdir = (skill_dir / workdir).resolve()
    else:
        workdir = workdir.resolve()

    data_dir = Path(config.get("data_dir", default_data)).expanduser()
    if not data_dir.is_absolute():
        data_dir = (workdir / data_dir).resolve()
    else:
        data_dir = data_dir.resolve()

    output_dir = Path(config.get("output_dir", default_output)).expanduser()
    if not output_dir.is_absolute():
        output_dir = (workdir / output_dir).resolve()
    else:
        output_dir = output_dir.resolve()

    return skill_dir, workdir, data_dir, output_dir
