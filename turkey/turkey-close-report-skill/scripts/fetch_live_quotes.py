# -*- coding: utf-8 -*-
"""Fetch latest BIST, FX, gold and oil quotes from BloombergHT live pages."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BORSA_URL = "https://www.bloomberght.com/borsa/"
PIYASALAR_URL = "https://www.bloomberght.com/piyasalar"
TR_TZ = timezone(timedelta(hours=3))

# BHT is behind Cloudflare; a single TLS/5xx flap would silently drop live
# quotes from the morning report. Retry transparently.
_SESSION = requests.Session()
_RETRY = Retry(
    total=3,
    backoff_factor=1.5,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset({"GET", "HEAD"}),
    raise_on_status=False,
)
_SESSION.mount("https://", HTTPAdapter(max_retries=_RETRY))
_SESSION.mount("http://", HTTPAdapter(max_retries=_RETRY))

_QUOTE_RE = re.compile(
    r">(USD/TRY|EUR/TRY|ALTIN/ONS|GRAM ALTIN|BRENT)[^<]*</span>\s*"
    r'<span class="text-right">([\d.,]+)</span>\s*'
    r'<span class="text-right">([\d.,\-]+)</span>\s*'
    r'<span class="text-right">([\d.,\-]+)</span>',
    re.I,
)

# BIST 100 (XU100) snapshot in the top tab-button widget:
#   <span class="text-left">BIST 100</span>
#   <span class="text-right">13.501,55</span>   <- last
#   <span class="text-right">-186,31</span>     <- abs change
#   <span class="text-right">-1,36</span>       <- pct
# Captures (label, last, change, pct). Use to cross-check/override the BHT
# close-review article, which has been observed to publish stale or mistyped
# index numbers.
_INDEX_RE = re.compile(
    r'<span class="text-left">(BIST\s*100)</span>\s*'
    r'<span class="text-right">([\d.,]+)</span>\s*'
    r'<span class="text-right">([\d.,\-]+)</span>\s*'
    r'<span class="text-right">([\d.,\-]+)</span>',
    re.I,
)


def _tr_float(token: str) -> Optional[float]:
    t = (token or "").strip().replace(" ", "")
    if not t:
        return None
    if "," in t and "." in t:
        return float(t.replace(".", "").replace(",", "."))
    if "," in t:
        return float(t.replace(",", "."))
    if t.count(".") >= 2:
        parts = t.split(".")
        return float("".join(parts[:-1]) + "." + parts[-1])
    try:
        return float(t)
    except ValueError:
        return None


def _fmt(v: float) -> str:
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s


def parse_piyasalar_html(html: str) -> dict:
    """Parse last / abs-change / pct from piyasalar widget rows."""
    out: dict[str, dict] = {}
    for m in _QUOTE_RE.finditer(html or ""):
        key = m.group(1).upper().replace(" ", "_")
        last = _tr_float(m.group(2))
        chg = _tr_float(m.group(3))
        pct = _tr_float(m.group(4))
        if last is None:
            continue
        # first hit wins (widget tables repeat)
        if key not in out:
            out[key] = {"last": last, "change": chg, "pct": pct, "raw_last": m.group(2)}
    # BIST 100 (XU100) — separate structure from FX/gold/oil rows.
    # First match = top-of-page widget; contains last + abs change + pct.
    idx_m = _INDEX_RE.search(html or "")
    if idx_m:
        last = _tr_float(idx_m.group(2))
        chg = _tr_float(idx_m.group(3))
        pct = _tr_float(idx_m.group(4))
        if last is not None:
            out["XU100"] = {
                "last": last,
                "change": chg,
                "pct": pct,
                "raw_last": idx_m.group(2),
            }
    return out


def _table_rows(table) -> list[list[str]]:
    rows = []
    for row in table.find_all("tr"):
        cells = [
            cell.get_text(" ", strip=True)
            for cell in row.find_all(["th", "td"])
        ]
        if cells:
            rows.append(cells)
    return rows


def _stock_code(cell: str) -> str | None:
    match = re.search(r"\b[A-Z][A-Z0-9.]{2,7}\b", cell or "")
    return match.group(0) if match else None


def _parse_borsa_table(table, *, with_volume: bool = False) -> list[dict]:
    """Parse one /borsa stock table without depending on CSS class names."""
    rows = _table_rows(table)
    parsed = []
    for cells in rows[1:]:
        if len(cells) < 3:
            continue
        code = _stock_code(cells[0])
        last = _tr_float(cells[1])
        pct = _tr_float(cells[2])
        if not code or last is None:
            continue
        item = {"code": code, "last": last, "pct": pct}
        if with_volume and len(cells) >= 4:
            item["volume"] = _tr_int(cells[3])
        parsed.append(item)
    return parsed


def _tr_int(token: str) -> int | None:
    raw = (token or "").replace(" ", "").replace(",", "")
    digits = raw.replace(".", "")
    return int(digits) if digits.isdigit() else None


def parse_borsa_html(html: str) -> dict:
    """Parse the faster /borsa snapshot: XU100 and current stock movers."""
    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.find_all("table")
    result = {
        "url": BORSA_URL,
        "index": {},
        "gainers": [],
        "losers": [],
        "volume": [],
    }
    stock_tables = []

    for table in tables:
        rows = _table_rows(table)
        if not rows:
            continue
        header = " ".join(rows[0]).upper()
        body = " ".join(" ".join(row) for row in rows[:3]).upper()
        if "BIST" in body and "XU100" in body:
            for cells in rows[1:]:
                if not cells or "XU100" not in cells[0].upper():
                    continue
                if len(cells) >= 3:
                    last = _tr_float(cells[1])
                    pct = _tr_float(cells[2])
                    if last is not None:
                        result["index"] = {
                            "last": last,
                            "pct": pct,
                            "raw_last": cells[1],
                        }
                        break
            continue

        if "HİSSE ADI" not in header and "HISSE ADI" not in header:
            continue
        stock_tables.append(table)
        heading = table.find_previous(["h2", "h3", "h4", "h5"])
        label = heading.get_text(" ", strip=True).lower() if heading else ""
        if "artan" in label:
            result["gainers"] = _parse_borsa_table(table)
        elif "azalan" in label:
            result["losers"] = _parse_borsa_table(table)
        elif "işlem" in label or "islem" in label:
            result["volume"] = _parse_borsa_table(table, with_volume=True)

    # The desktop page has kept these three tables in a stable order, while
    # headings/classes have changed several times. Use order only as a
    # fallback, never as the primary classifier.
    if stock_tables:
        if not result["gainers"] and len(stock_tables) >= 1:
            result["gainers"] = _parse_borsa_table(stock_tables[0])
        if not result["losers"] and len(stock_tables) >= 2:
            result["losers"] = _parse_borsa_table(stock_tables[1])
        if not result["volume"] and len(stock_tables) >= 3:
            result["volume"] = _parse_borsa_table(stock_tables[2], with_volume=True)

    return result


def format_borsa_snapshot_cn(borsa: dict) -> str:
    """Chinese facts for current stock movers from /borsa."""
    lines = [
        "【BHT实时行情卡｜/borsa｜仅供【大盘概况】【关键个股异动】"
        "复述；禁止分析与补数】"
    ]
    index = borsa.get("index") or {}
    if index.get("last") is not None:
        pct = index.get("pct")
        pct_text = f"，变动 {_fmt(pct)}%" if pct is not None else ""
        lines.append(f"XU100最新点位 {_fmt(index['last'])}{pct_text}。")

    volume = borsa.get("volume") or []
    if volume:
        parts = []
        for item in volume[:3]:
            amount = item.get("volume")
            if amount is not None:
                parts.append(f"{item['code']} {amount / 1e8:.2f}".rstrip("0").rstrip(".") + "亿里拉")
        if parts:
            lines.append("实时成交额前三：" + "，".join(parts) + "。")

    for label, key in (("实时涨幅居前", "gainers"), ("实时跌幅居前", "losers")):
        items = borsa.get(key) or []
        if not items:
            continue
        parts = []
        for item in items[:5]:
            pct = item.get("pct")
            suffix = f"（{_fmt(pct)}%）" if pct is not None else ""
            parts.append(f"{item['code']}{suffix}")
        lines.append(label + "：" + "、".join(parts) + "。")
    return "\n".join(lines)


def _classify_xu100_time(now_tr: datetime) -> str:
    if now_tr.weekday() >= 5 or now_tr.hour < 10:
        return "pre_market"
    if now_tr.hour < 18 or (now_tr.hour == 18 and now_tr.minute < 30):
        return "intraday"
    return "after_close"


def format_live_quotes_cn(quotes: dict) -> str:
    """Chinese fact lines for 【汇市与大宗商品】 — no clock stamps, no analysis."""
    lines = [
        "【最新报价事实｜仅供【汇市与大宗商品】复述；禁止写钟点；禁止分析与补数】"
    ]
    usd = quotes.get("USD/TRY")
    eur = quotes.get("EUR/TRY")
    fx = []
    if usd:
        pct = usd.get("pct")
        bit = f"美元/里拉报 {_fmt(usd['last'])}"
        if pct is not None:
            sign = "+" if pct >= 0 else ""
            bit += f"，变动 {sign}{_fmt(pct)}%"
        fx.append(bit)
    if eur:
        pct = eur.get("pct")
        bit = f"欧元/里拉报 {_fmt(eur['last'])}"
        if pct is not None:
            sign = "+" if pct >= 0 else ""
            bit += f"，变动 {sign}{_fmt(pct)}%"
        fx.append(bit)
    if fx:
        lines.append("；".join(fx) + "。")

    oz = quotes.get("ALTIN/ONS")
    gram = quotes.get("GRAM_ALTIN") or quotes.get("GRAM ALTIN")
    gold = []
    if oz:
        pct = oz.get("pct")
        bit = f"国际金价报 {_fmt(oz['last'])} 美元/盎司"
        if pct is not None:
            sign = "+" if pct >= 0 else ""
            bit += f"，变动 {sign}{_fmt(pct)}%"
        gold.append(bit)
    if gram:
        pct = gram.get("pct")
        bit = f"克金报 {_fmt(gram['last'])} 里拉"
        if pct is not None:
            sign = "+" if pct >= 0 else ""
            bit += f"，变动 {sign}{_fmt(pct)}%"
        gold.append(bit)
    if gold:
        lines.append("；".join(gold) + "。")

    brent = quotes.get("BRENT")
    if brent:
        pct = brent.get("pct")
        bit = f"布伦特报 {_fmt(brent['last'])} 美元"
        if pct is not None:
            sign = "+" if pct >= 0 else ""
            bit += f"，变动 {sign}{_fmt(pct)}%"
        lines.append(bit + "。")

    if len(lines) == 1:
        lines.append("（最新报价抓取失败或页面结构变化）")
    return "\n".join(lines)


def fetch_live_quotes(
    cache_dir: Path,
    *,
    url: str = PIYASALAR_URL,
    use_cache: bool = False,
) -> dict:
    """
    Fetch BIST/stock movers from /borsa first, then FX/commodities from
    /piyasalar. By default always refresh; optional cache is for debug only.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "live_quotes_latest.json"

    if use_cache and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if cached.get("ok") and cached.get("quotes"):
                return cached
        except Exception:
            pass

    now_tr_dt = datetime.now(TR_TZ)
    now_tr = now_tr_dt.isoformat()
    borsa = {}
    borsa_error = None
    try:
        borsa_resp = _SESSION.get(BORSA_URL, timeout=30)
        borsa_resp.raise_for_status()
        borsa = parse_borsa_html(borsa_resp.text)
    except Exception as exc:
        borsa_error = str(exc)
        print(f"BHT /borsa fetch failed: {exc}", file=sys.stderr)

    quotes = {}
    piyasalar_error = None
    try:
        resp = _SESSION.get(url, timeout=30)
        resp.raise_for_status()
        quotes = parse_piyasalar_html(resp.text)
    except Exception as exc:
        piyasalar_error = str(exc)
        print(f"BHT /piyasalar fetch failed: {exc}", file=sys.stderr)

    if not borsa.get("index") and quotes.get("XU100"):
        borsa["index"] = quotes["XU100"]
    ok = bool(
        quotes.get("USD/TRY")
        or quotes.get("ALTIN/ONS")
        or quotes.get("BRENT")
        or borsa.get("index")
    )
    xu100_status = _classify_xu100_time(now_tr_dt)
    errors = [error for error in (borsa_error, piyasalar_error) if error]
    payload = {
        "ok": ok,
        "fetched_at_tr": now_tr,
        "xu100_status": xu100_status,
        "url": url,
        "source_urls": {"borsa": BORSA_URL, "piyasalar": url},
        "borsa_ok": bool(borsa.get("index")),
        "piyasalar_ok": bool(
            quotes.get("USD/TRY") or quotes.get("ALTIN/ONS") or quotes.get("BRENT")
        ),
        "quotes": quotes,
        "borsa": borsa,
        "borsa_fact_cn": format_borsa_snapshot_cn(borsa),
        "fact_cn": format_live_quotes_cn(quotes) if quotes else "",
        "error": None if ok else ("; ".join(errors) or "parse_empty"),
    }

    cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    data = fetch_live_quotes(root / ".cache" / "turkey-close-report")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
    print(data.get("fact_cn", ""))
