#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared runtime helpers for portable skill execution."""
from __future__ import annotations

import sys
from pathlib import Path


def configure_stdio() -> None:
    """Force UTF-8 stdout/stderr so Unicode text works on Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def resolve_paths(
    config_path: Path,
    config: dict,
    *,
    default_cache: str,
    default_output: str = "output",
) -> tuple[Path, Path, Path, Path]:
    """
    Resolve skill/work/output/cache paths from config.

    `workdir` is relative to the skill directory (where config.json lives) unless absolute.
    """
    config_path = config_path.resolve()
    skill_dir = config_path.parent

    workdir = Path(config.get("workdir", ".")).expanduser()
    if not workdir.is_absolute():
        workdir = (skill_dir / workdir).resolve()
    else:
        workdir = workdir.resolve()

    output_dir = Path(config.get("output_dir", default_output))
    if not output_dir.is_absolute():
        output_dir = (workdir / output_dir).resolve()

    cache_dir = Path(config.get("cache_dir", default_cache))
    if not cache_dir.is_absolute():
        cache_dir = (workdir / cache_dir).resolve()

    return skill_dir, workdir, output_dir, cache_dir
