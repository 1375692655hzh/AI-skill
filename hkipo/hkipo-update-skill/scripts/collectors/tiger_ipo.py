#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tiger Brokers (老虎证券) HK IPO JSON collector.

Surface: https://hktrade.skytigris.com/ipos/general/hk?status=OPEN|LISTED&lang=zh_CN

Free, no auth, returns JSON with the richest structured IPO fields available:
symbol, OfferingSize, minQty (board lot), minPrice, maxPrice, closingDate (epoch ms),
allotmentDate, listDate, greyOpeningTime, greyClosingTime, prospectusUrl, etc.

This module is responsible for hitting both OPEN (in offer) and LISTED
(for recent debut tracking) status filters and merging them.
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


def fetch_tiger_status(
    endpoint: str,
    status_filter: str,
    snapshot_dir: Path,
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> List[Dict[str, Any]]:
    """GET endpoint?status=<OPEN|LISTED>&lang=zh_CN. Save raw to snapshot_dir."""
    url = f"{endpoint.rstrip('/')}"
    params = {"status": status_filter, "lang": "zh_CN"}
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Referer": "https://www.itiger.com/",
    }
    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    out_path = snapshot_dir / f"tiger_{status_filter.lower()}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Tiger payload shapes observed in the wild: top-level `data` list, or
    # `data.items`, or sometimes `data.list`. Be tolerant.
    data_node = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(data_node, dict):
        items = (
            data_node.get("items")
            or data_node.get("list")
            or data_node.get("ipos")
            or data_node.get("results")
            or []
        )
    else:
        items = data_node or []

    return [i for i in items if isinstance(i, dict)]


def collect(
    cfg: Dict[str, Any],
    snapshot_dir: Path,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Entry point. Returns (list_of_ipo_items, status_dict)."""
    status: Dict[str, str] = {}
    if not cfg.get("enabled", True):
        status["tiger_json"] = "disabled"
        return [], status

    endpoint = cfg.get("endpoint") or "https://hktrade.skytigris.com/ipos/general/hk"
    out: List[Dict[str, Any]] = []
    failures: List[str] = []

    for sf in ("OPEN", "LISTED"):
        try:
            items = fetch_tiger_status(endpoint, sf, snapshot_dir)
            for item in items:
                # Carry the explicit status into the normalized row
                item.setdefault("status", sf)
            out.extend(items)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{sf}:{type(exc).__name__}")

    if failures and not out:
        status["tiger_json"] = f"degraded:{','.join(failures)}"
    elif failures:
        status["tiger_json"] = f"partial:{','.join(failures)}"
    else:
        status["tiger_json"] = "ok"
    return out, status
