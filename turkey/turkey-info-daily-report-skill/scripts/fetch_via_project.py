#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional fetcher via Turkey-investment project cache or CLI."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path


KIND_MAP = {
    "info-daily": ("daily", "infoyatirim_daily_bulletin"),
    "info-technical": ("technical", "infoyatirim_technical_bulletin"),
}


def _read_local_report(workdir: Path, target_date: date, position: str) -> str:
    """Read already-fetched markdown from Turkey-investment reports directory."""
    iso = target_date.isoformat()
    candidates = [
        workdir / "reports" / "turkey-market-reports" / iso / f"{iso}_{position}.md",
        workdir / "reports" / "turkey-market-reports" / iso / f"{iso}_{position.replace('infoyatirim_', 'infoyatirim_')}.md",
    ]
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8")

    manifest = workdir / "reports" / "turkey-market-reports" / iso / f"{iso}_manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            for entry in data.get("files", []):
                if entry.get("position") == position.replace("infoyatirim_", "").replace("_bulletin", "_bulletin"):
                    rel = entry.get("file_path") or entry.get("path") or ""
                    if rel.endswith(".md"):
                        p = Path(rel)
                        if not p.is_absolute():
                            p = workdir / p
                        if p.is_file():
                            return p.read_text(encoding="utf-8")
                if position.split("_")[-2] in (entry.get("position") or "") and (entry.get("file_path") or "").endswith(".md"):
                    p = Path(entry["file_path"])
                    if not p.is_absolute():
                        p = workdir / p
                    if p.is_file():
                        return p.read_text(encoding="utf-8")
        except Exception:
            pass
    return ""


def _run_project_cli(workdir: Path, kind: str, target_date: date) -> dict:
    script_kind, position = KIND_MAP[kind]
    script = workdir / "info_yatirim_reports.py"
    if not script.is_file():
        return {"ok": False, "reason": "project_not_found"}

    cmd = [
        sys.executable,
        str(script),
        script_kind,
        target_date.isoformat(),
        "--json",
        "--out-dir",
        str(workdir / "reports" / "turkey-market-reports"),
        "--quiet",
    ]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            env=env,
        )
    except Exception as exc:
        print(f"Warning: project fetch failed: {exc}", file=sys.stderr)
        return {"ok": False, "reason": "project_fetch_error"}

    stdout = proc.stdout or ""
    if proc.returncode != 0 and not stdout.strip().startswith("{"):
        stderr = (proc.stderr or "")[:500]
        print(f"Warning: project fetch exit {proc.returncode}: {stderr}", file=sys.stderr)
        return {"ok": False, "reason": "project_fetch_failed", "stderr": stderr}

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        content = _read_local_report(workdir, target_date, position)
        if content:
            return _pack_result(target_date, content, data={"file_path": str(workdir)})
        return {"ok": False, "reason": "invalid_json"}

    if not data.get("ok"):
        content = _read_local_report(workdir, target_date, position)
        if content:
            return _pack_result(target_date, content, data=data)
        return {
            "ok": False,
            "reason": data.get("reason", "not_found"),
            "fallback_url": data.get("fallback_url", ""),
        }

    content = data.get("markdown") or ""
    if not content and data.get("file_path"):
        file_path = Path(data["file_path"])
        if not file_path.is_absolute():
            file_path = workdir / file_path
        if file_path.is_file():
            content = file_path.read_text(encoding="utf-8")
    if not content:
        content = _read_local_report(workdir, target_date, position)

    if not content:
        return {"ok": False, "reason": "empty_content"}

    return _pack_result(target_date, content, data=data)


def _pack_result(target_date: date, content: str, *, data: dict) -> dict:
    return {
        "ok": True,
        "reason": "ok",
        "target_date": target_date.isoformat(),
        "uuid": data.get("uuid", ""),
        "url": data.get("url", ""),
        "fallback_url": data.get("fallback_url", data.get("url", "")),
        "content": content,
        "file_path": data.get("file_path", ""),
        "fetch_source": "turkey-investment",
    }


def fetch_info_via_project(command: str, target_date: date, workdir: Path) -> dict:
    """
    Prefer local Turkey-investment reports; otherwise call info_yatirim_reports.py.
    """
    if command not in KIND_MAP:
        return {"ok": False, "reason": "unknown_command"}

    _, position = KIND_MAP[command]
    local = _read_local_report(workdir, target_date, position)
    if local:
        return _pack_result(target_date, local, data={"file_path": str(workdir)})

    return _run_project_cli(workdir, command, target_date)
