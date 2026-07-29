# -*- coding: utf-8 -*-
"""Fetch latest FX / gold / oil quotes from BloombergHT live market page."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
    return out


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
    Fetch latest quotes from BloombergHT /piyasalar.
    By default always refresh (morning needs latest); optional short cache for debug.
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

    now_tr = datetime.now(TR_TZ).isoformat()
    try:
        resp = _SESSION.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; turkey-morning-report/1.0)"},
            timeout=40,
        )
        resp.raise_for_status()
        quotes = parse_piyasalar_html(resp.text)
        ok = bool(quotes.get("USD/TRY") or quotes.get("ALTIN/ONS") or quotes.get("BRENT"))
        payload = {
            "ok": ok,
            "fetched_at_tr": now_tr,
            "url": url,
            "quotes": quotes,
            "fact_cn": format_live_quotes_cn(quotes) if ok else "",
            "error": None if ok else "parse_empty",
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "fetched_at_tr": now_tr,
            "url": url,
            "quotes": {},
            "fact_cn": "",
            "error": str(exc),
        }
        print(f"Live quotes fetch failed: {exc}", file=sys.stderr)

    cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    data = fetch_live_quotes(root / ".cache" / "turkey-morning-report")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
    print(data.get("fact_cn", ""))
