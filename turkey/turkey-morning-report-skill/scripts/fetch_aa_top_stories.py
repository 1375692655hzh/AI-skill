# -*- coding: utf-8 -*-
"""Fetch Anadolu Agency Morning Briefing TOP STORIES for morning-report news card."""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional


def _aa_scripts_dir(skill_dir: Path | None = None) -> Optional[Path]:
    """Resolve sibling turkey-aa-morning-briefing-skill/scripts."""
    here = Path(__file__).resolve().parent.parent  # turkey-morning-report-skill
    candidates = []
    if skill_dir:
        candidates.append(Path(skill_dir) / "scripts")
    candidates.extend(
        [
            here.parent / "turkey-aa-morning-briefing-skill" / "scripts",
            here / "vendor" / "turkey-aa-morning-briefing-skill" / "scripts",
        ]
    )
    for p in candidates:
        if (p / "fetch_aa_morning_briefing.py").is_file():
            return p
    return None


def extract_top_story_titles(top_stories_body: str) -> list[str]:
    """Parse AA TOP STORIES block into headline lines (first line of each bullet)."""
    body = (top_stories_body or "").replace("\r\n", "\n")
    parts = re.split(r"(?m)^-\s+", body)
    titles: list[str] = []
    for part in parts[1:]:
        first = part.strip().split("\n")[0].strip()
        # Drop trailing ":" report labels noise lightly
        first = re.sub(r"\s*:\s*Report\s*$", "", first, flags=re.I).strip()
        if first and len(first) > 12:
            titles.append(first)
    return titles


def fetch_aa_top_stories(
    briefing_date: date,
    cache_dir: Path,
    *,
    aa_skill_dir: str | None = None,
    force_refresh: bool = False,
) -> dict:
    """
    Fetch AA English Morning Briefing and return TOP STORIES headlines.
    Uses sibling AA skill fetcher when available.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"aa_top_stories_{briefing_date.isoformat()}.json"
    if cache_file.exists() and not force_refresh:
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if cached.get("ok") and cached.get("titles"):
                return cached
        except Exception:
            pass

    scripts = _aa_scripts_dir(Path(aa_skill_dir) if aa_skill_dir else None)
    if not scripts:
        payload = {
            "ok": False,
            "titles": [],
            "url": "",
            "error": "aa_skill_not_found",
            "date": briefing_date.isoformat(),
        }
        cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Warning: turkey-aa-morning-briefing-skill not found; skip AA news.", file=sys.stderr)
        return payload

    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))

    try:
        from fetch_aa_morning_briefing import fetch_aa_morning_briefing
        from reorder_sections import split_sections
    except Exception as exc:
        payload = {
            "ok": False,
            "titles": [],
            "url": "",
            "error": f"import_failed:{exc}",
            "date": briefing_date.isoformat(),
        }
        cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    aa_cache = cache_dir / "aa-briefing"
    try:
        article = fetch_aa_morning_briefing(
            briefing_date,
            aa_cache,
            force_refresh=force_refresh,
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "titles": [],
            "url": "",
            "error": str(exc),
            "date": briefing_date.isoformat(),
        }
        cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Warning: AA fetch failed: {exc}", file=sys.stderr)
        return payload

    if not article.get("ok"):
        payload = {
            "ok": False,
            "titles": [],
            "url": article.get("url") or "",
            "error": article.get("reason") or article.get("error") or "aa_not_ok",
            "date": briefing_date.isoformat(),
        }
        cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Warning: AA briefing missing for {briefing_date}: {payload['error']}", file=sys.stderr)
        return payload

    body = article.get("content") or article.get("content_original") or ""
    _, sections = split_sections(body)
    top_body = ""
    for name, sec_body in sections:
        if name == "TOP STORIES":
            top_body = sec_body
            break

    titles = extract_top_story_titles(top_body)
    payload = {
        "ok": bool(titles),
        "titles": titles,
        "url": article.get("url") or "",
        "published": (article.get("published") or {}).get("tr") or "",
        "date": briefing_date.isoformat(),
        "error": None if titles else "top_stories_empty",
        "source": "aa_top_stories",
    }
    cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
