#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract BIST tickers mentioned in Turkish broker commentary text."""
from __future__ import annotations

import re
from typing import Iterable

# Common false positives to ignore.
STOPWORDS = {
    "BIST", "VIOP", "XU030", "XU100", "ABD", "FED", "TCMB", "TRY", "USD", "EUR",
    "ONS", "WTI", "RSI", "MACD", "CCI", "GDP", "IPO", "ETF", "CEO", "TÜFE", "TUFE",
    "HAFT", "GÜN", "GUN", "YIL", "AY", "TL", "TR", "NET", "AL", "SAT", "VAR", "YOK",
}

# High-coverage BIST tickers (BIST30 + liquid BIST100). Extend as needed.
KNOWN_TICKERS = {
    "AEFES", "AGHOL", "AKBNK", "AKSA", "AKSEN", "ALARK", "ALTNY", "ANSGR", "ARCLK",
    "ASELS", "ASTOR", "AYGAZ", "BALSU", "BIMAS", "BRSAN", "BRYAT", "BSOKE", "BTCIM",
    "CANTE", "CCOLA", "CIMSA", "CWENE", "DOAS", "DOHOL", "DSTKF", "ECILC", "EFOR",
    "EKGYO", "ENERY", "ENJSA", "ENKAI", "EREGL", "EUPWR", "FROTO", "GARAN", "GESAN",
    "GUBRF", "HALKB", "HEKTS", "ISCTR", "ISMEN", "KCHOL", "KONTR", "KRDMD", "KTLEV",
    "MAGEN", "MAVI", "MGROS", "MIATK", "MPARK", "ODAS", "OTKAR", "OYAKC", "PETKM",
    "PGSUS", "QUAGR", "RALYH", "SAHOL", "SASA", "SISE", "SKBNK", "SOKM", "TAVHL",
    "TCELL", "THYAO", "TKFEN", "TOASO", "TRALT", "TRENJ", "TRMET", "TSKB", "TTKOM",
    "TUKAS", "TUPRS", "TUREX", "TURSG", "ULKER", "VAKBN", "VESTL", "YKBNK", "ZOREN",
    "GENIL", "GLRMK", "GRSEL", "GRTHO", "GSRAY", "IZENR", "KLRHO", "KUYAS", "OBAMS",
    "PASEU", "PATEK", "PSGYO", "REEDR", "SARKY", "TABGD", "EUREN", "CVKMD", "DAPGM",
    "BIMAS", "LOGO", "ASELSAN",
}

TICKER_RE = re.compile(r"\b[A-ZÇĞİÖŞÜ]{2,6}\b")


def extract_tickers(text: str, *, extra: Iterable[str] | None = None) -> list[str]:
    if not text:
        return []
    pool = set(KNOWN_TICKERS)
    if extra:
        pool.update(extra)
    hits: list[str] = []
    seen: set[str] = set()
    for m in TICKER_RE.finditer(text.upper().replace("İ", "I").replace("Ş", "S").replace("Ğ", "G").replace("Ü", "U").replace("Ö", "O").replace("Ç", "C")):
        tok = m.group(0)
        if tok in STOPWORDS or tok not in pool:
            continue
        if tok not in seen:
            seen.add(tok)
            hits.append(tok)
    return hits


def tickers_by_article(articles: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for art in articles:
        if art.get("fetch_status") != "ok":
            continue
        key = art.get("broker_slug") or art.get("slug", "")
        out[key] = extract_tickers(art.get("content", ""))
    return out
