#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HKEX Application Proof / PHIP index collector.

HKEX renders the appindex.html page client-side from 4 server-rendered JSON files
under https://www1.hkexnews.hk/ncms/json/eds/:
  - appactive_app_sehk_c.json        — Active Application Proofs (新递表，等聆讯)
  - appactive_appphip_sehk_c.json    — Active PHIPs (聆讯通过，待招股)
  - applisted_sehk_c.json            — Listed (已上市)
  - appreturned_sehk_c.json          — Returned (退回)

Field reference (per applicant row):
  id           HKEX numeric ID
  d            filing date DD/MM/YYYY
  a            applicant name (中文 for _c.json)
  s            status token: "A"=active, "LT"=listed
  w            warning PDF relative path
  sD / sA      internal counters
  ls           linked materials list (each: d / nF=doctype / nS1 / nS2 / u1 / u2)
  ps           post-listing materials
  hasPhip      boolean — already passed hearing
  postingDate  "Mon DD, YYYY" string
  st           stock code (only on applisted rows, e.g. "01396")

This collector fetches all four files, normalizes to one list of dicts ready
for lib/normalize.normalize_hkex_appindex, and writes raw snapshots for audit.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

HK_TZ = timezone(timedelta(hours=8))

DEFAULT_TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# All four surfaces, each tagged with the canonical HKIPO status it represents
SURFACES = [
    ("appactive_app_sehk_c.json", "active_application_proof"),     # filed, awaiting hearing
    ("appactive_appphip_sehk_c.json", "active_phip"),              # passed hearing
    ("applisted_sehk_c.json", "listed"),                           # already listed
    ("appreturned_sehk_c.json", "returned"),                       # returned (rare)
]

DEFAULT_JSON_BASE = "https://www1.hkexnews.hk/ncms/json/eds/"


def _parse_date_ddmmyyyy(s: str) -> str:
    """'17/10/2025' → '2025-10-17'. Pass through if already ISO."""
    if not s:
        return ""
    try:
        return datetime.strptime(s, "%d/%m/%Y").date().isoformat()
    except ValueError:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date().isoformat()
        except ValueError:
            return s


def extract_milestone_dates(ls: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Pull (ap_date, phip_date) from an applicant's `ls[]` linked-materials list.

    Ported from HKIPO project's `hkex_client.extract_milestone_dates`. Each `ls`
    item carries a doctype label `nF`:
      - '申請版本' / '申请版本' → Application Proof filing (首次递表)
      - '聆訊' / '聆讯'        → Post-Hearing Information Pack (PHIP)

    Returns (earliest_ap_date, latest_phip_date) as ISO strings. Either may be
    empty if the corresponding milestone has no entry.
    """
    ap_candidates: List[str] = []
    phip_candidates: List[str] = []
    for item in ls or []:
        nf = (item.get("nF") or "").strip()
        d_raw = item.get("d", "")
        if not d_raw:
            continue
        d = _parse_date_ddmmyyyy(d_raw)
        if not d:
            continue
        if "申請版本" in nf or "申请版本" in nf:
            ap_candidates.append(d)
        if "聆訊" in nf or "聆讯" in nf:
            phip_candidates.append(d)
    ap_date = min(ap_candidates) if ap_candidates else ""
    phip_date = max(phip_candidates) if phip_candidates else ""
    return ap_date, phip_date


def _latest_prospectus_link(ls: List[Dict[str, Any]]) -> Tuple[str, str]:
    """From `ls` (linked materials), pick the most recent prospectus / PHIP PDF.

    Returns (relative_pdf_path, doctype_label). Empty strings if none.
    """
    candidates = []
    for item in ls or []:
        doctype = (item.get("nF") or "")
        # Application Proof / PHIP / Path Prospectus all qualify
        if any(kw in doctype for kw in
               ("申請版本", "申請版", "聆訊後資料集", "PHIP", "Application Proof", "Post-Hearing", "上市文件", "招股書")):
            u1 = item.get("u1") or item.get("u2")
            if u1:
                try:
                    sort_date = _parse_date_ddmmyyyy(item.get("d") or "")
                except Exception:  # noqa: BLE001
                    sort_date = ""
                candidates.append((sort_date, u1, doctype))
    if not candidates:
        return "", ""
    candidates.sort(reverse=True)
    return candidates[0][1], candidates[0][2]


def fetch_surface(filename: str, json_base: str, snapshot_dir: Path, *, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Fetch one HKEX JSON file. Save raw to snapshot_dir/{filename}."""
    url = json_base.rstrip("/") + "/" + filename
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / filename).write_text(resp.text, encoding="utf-8")
    return resp.json()


def _normalize_row(item: Dict[str, Any], surface_tag: str) -> Dict[str, Any]:
    """Map one raw HKEX row to lib/normalize.normalize_hkex_appindex input."""
    ls = item.get("ls") or []
    prospectus_url, _ = _latest_prospectus_link(ls)
    if prospectus_url and not prospectus_url.startswith("http"):
        prospectus_url = "https://www1.hkexnews.hk/" + prospectus_url.lstrip("/")
    ap_date, phip_date = extract_milestone_dates(ls)
    return {
        "stock_code": item.get("st") or "",            # empty for non-listed
        "name_zh": item.get("a"),
        "filing_date": _parse_date_ddmmyyyy(item.get("d") or ""),
        "ap_date": ap_date,                             # 首次递表 (from ls[], ISO)
        "phip_date": phip_date,                         # 聆讯 (from ls[], ISO)
        "has_phip": bool(item.get("hasPhip")),
        "state": surface_tag,
        "status_token": item.get("s"),
        "posting_date": item.get("postingDate"),
        "hkex_id": str(item.get("id") or ""),
        "prospectus_url": prospectus_url or None,
        "return_date": _parse_date_ddmmyyyy(item.get("rd") or "") if surface_tag == "returned" else None,
    }


def collect(
    cfg: Dict[str, Any],
    snapshot_dir: Path,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Entry point called by run_update.py."""
    status: Dict[str, str] = {}
    if not cfg.get("enabled", True):
        status["hkex_appindex"] = "disabled"
        return [], status

    # Old config had `endpoint`; new is `json_base` (defaults to HKEX eds dir)
    json_base = cfg.get("json_base") or DEFAULT_JSON_BASE
    # Backward-compat: if user only set `endpoint` to the appindex.html page,
    # ignore it (we now use the JSON dir directly)
    surfaces = cfg.get("surfaces") or SURFACES

    out: List[Dict[str, Any]] = []
    failures: List[str] = []
    for filename, tag in surfaces:
        try:
            data = fetch_surface(filename, json_base, snapshot_dir)
            rows = data.get("app") or []
            for item in rows:
                if isinstance(item, dict):
                    out.append(_normalize_row(item, tag))
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{filename}:{type(exc).__name__}")

    if failures and not out:
        status["hkex_appindex"] = f"degraded:{','.join(failures)}"
    elif failures:
        status["hkex_appindex"] = f"partial:{','.join(failures)}"
    else:
        status["hkex_appindex"] = f"ok:{len(out)}"
    return out, status
