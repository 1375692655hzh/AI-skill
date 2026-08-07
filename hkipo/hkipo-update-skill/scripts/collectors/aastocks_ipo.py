#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AAStocks HK IPO centre collector.

Surface: https://hk.aastocks.com/sc/stocks/market/ipo/mainpage.aspx
  - 正在招股 (IPOIPOList?svc=ipoing)
  - 擬上市新股 (IPOIPOList?svc=coming)
  - 已上市新股 (IPOIPOList?svc=listed)

Server-rendered HTML tables — the most reliable free web source for cross-check
of offer price / board lot / listing date / grey-market price. Used here as
SUPPLEMENTARY source: missing Tiger fields get filled by AAStocks.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

LIST_URL_TEMPLATE = "{base}/IPOIPOList.aspx?svc={svc}&lang=zh-CN"


def _fetch_html(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    # AAStocks is Big5/UTF-8 mixed; prefer utf-8 then fall back to detected encoding
    if resp.encoding and resp.encoding.lower() not in ("utf-8", "utf8"):
        resp.encoding = "utf-8"
    return resp.text


def _parse_ipo_table(html: str, svc: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows_out: List[Dict[str, Any]] = []
    for table in soup.find_all("table"):
        header_row = table.find("tr")
        if not header_row:
            continue
        header_text = header_row.get_text(" ", strip=True)
        if "招股價" not in header_text and "股票名稱" not in header_text and "編號" not in header_text:
            continue

        rows = table.find_all("tr")[1:]
        for tr in rows:
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if not cells or len(cells) < 2:
                continue
            # AAStocks tables have shape: [編號, 股票名稱, 招股價, 每手股數, 截止日期, 上市日期, ...]
            item: Dict[str, Any] = {"source_table": svc}
            if cells and re.match(r"^\d{4,5}$", cells[0]):
                item["stock_code"] = cells[0]
                if len(cells) > 1:
                    item["name_zh"] = cells[1]
                if len(cells) > 2:
                    item["price_text"] = cells[2]
                if len(cells) > 3:
                    item["board_lot_text"] = cells[3]
                if len(cells) > 4:
                    item["close_text"] = cells[4]
                if len(cells) > 5:
                    item["listing_text"] = cells[5]
                rows_out.append(item)
    return rows_out


def _parse_price(text: str) -> Tuple[Any, Any]:
    """'1.50 – 2.00' → (1.50, 2.00); '1.80' → (1.80, 1.80)."""
    if not text:
        return None, None
    nums = re.findall(r"\d+\.\d+|\d+", text.replace(",", ""))
    if not nums:
        return None, None
    if len(nums) == 1:
        return float(nums[0]), float(nums[0])
    return float(nums[0]), float(nums[-1])


def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    code = row.get("stock_code")
    if not code:
        return out
    out["stock_code"] = code
    out["name_zh"] = row.get("name_zh")
    lo, hi = _parse_price(row.get("price_text") or "")
    if lo is not None:
        out["price_low"] = lo
    if hi is not None:
        out["price_high"] = hi
    # board lot text "500" → int
    lot_text = row.get("board_lot_text") or ""
    m = re.search(r"\d+", lot_text.replace(",", ""))
    if m:
        out["board_lot"] = int(m.group(0))
    # Close date text → keep raw, normalize.py will parse
    if row.get("close_text"):
        out["status"] = "正在招股"
        out["close_text"] = row["close_text"]
    if row.get("listing_text"):
        out["listing_date"] = row["listing_text"]
    if row.get("source_table") == "coming":
        out["status"] = "擬上市"
    elif row.get("source_table") == "listed":
        out["status"] = "已上市"
    return out


def collect(
    cfg: Dict[str, Any],
    snapshot_dir: Path,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Entry point. Returns (list_of_normalized_rows, status_dict)."""
    status: Dict[str, str] = {}
    if not cfg.get("enabled", True):
        status["aastocks"] = "disabled"
        return [], status

    base = (cfg.get("base_url") or "https://hk.aastocks.com/sc/stocks/market/ipo").rstrip("/")
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    out: List[Dict[str, Any]] = []
    failures: List[str] = []

    for svc in ("ipoing", "coming", "listed"):
        url = LIST_URL_TEMPLATE.format(base=base, svc=svc)
        try:
            html = _fetch_html(url)
            (snapshot_dir / f"aastocks_{svc}.html").write_text(html, encoding="utf-8")
            parsed = _parse_ipo_table(html, svc)
            for row in parsed:
                norm = _normalize_row(row)
                if norm:
                    out.append(norm)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{svc}:{type(exc).__name__}")

    if failures and not out:
        status["aastocks"] = f"degraded:{','.join(failures)}"
    elif failures:
        status["aastocks"] = f"partial:{','.join(failures)}"
    else:
        status["aastocks"] = "ok"
    return out, status
