#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HKEX prospectus PDF parser — extracts 預期時間表 (Expected Timetable) dates.

Pattern set ported from the HKIPO project's `ipo_lifecycle.py`, which has been
battle-tested against hundreds of real prospectus PDFs and handles:
  - OCR spacing inside CJK tokens (「開 始 買 賣」)
  - Spacing inside CN date digits (「2026 年 6 月 30 日」)
  - Multiple phrasings of the same milestone (definition paragraphs, timetable
    rows, allotment-result announcements)
  - Loose matches guarded by a ±1 year sanity check

The Expected Timetable covers:
  offer_open_date   公开发售开始 / 招股开始
  cash_close_date   截止办理申请登记 / 完成电子申请的截止时间
  allotment_date    公布配发结果
  refund_date       寄发退款 / 资金解冻
  listing_date      开始买卖 / 预期将于 … 在联交所买卖

Margin financing (融资截止) is NOT published by HKEX — derived in
compute_events.py as cash_close − 1 *natural* day (per HKIPO project).

This collector also resolves prospectus URLs via HKEXnews title search when
a company row lacks one.
"""
from __future__ import annotations

import io
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

DEFAULT_TIMEOUT = 45
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_CN_DATE_RE = re.compile(
    r"(?P<y>20\d{2})\s*年\s*(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*日"
)
_ISO_DATE_RE = re.compile(r"(?P<y>20\d{2})-(?P<m>\d{1,2})-(?P<d>\d{1,2})")
_CN_DATE_CAP = r"(20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)"


# ---------------------------------------------------------------------------
# Pattern set (ported from HKIPO ipo_lifecycle.py)
# ---------------------------------------------------------------------------

# Expected listing / dealings commence
_LISTING_PATTERNS = [
    # HKEX canonical timetable row: 「預期股份開始於聯交所買賣 ........ 2026年7月13日」
    # Put this FIRST — it's the most common timetable-row phrasing in real prospectuses.
    re.compile(
        rf"預期股份開始於聯交所買賣[.．…·\.\s\|]{{0,200}}{_CN_DATE_CAP}",
        re.I,
    ),
    re.compile(
        rf"预期股份开始于联交所买卖[.．…·\.\s\|]{{0,200}}{_CN_DATE_CAP}",
        re.I,
    ),
    # Shorter variant: 「開始買賣..........2026年6月30日」
    re.compile(
        rf"開始買賣[.．…·\.\s\|]{{2,200}}{_CN_DATE_CAP}",
        re.I,
    ),
    re.compile(
        rf"预期.{{0,16}}?将于\s*{_CN_DATE_CAP}"
        r".{0,40}?开始(?:在)?(?:香港)?联交所买卖",
        re.I | re.S,
    ),
    re.compile(
        rf"預期.{{0,16}}?將於\s*{_CN_DATE_CAP}"
        r".{0,40}?開始(?:在)?(?:香港)?聯交所買賣",
        re.I | re.S,
    ),
    # 「上市日期」指…買賣的日期，預期將為2026年7月9日
    re.compile(
        rf"(?:買賣的日期|上市日期)[，,\s]{{0,6}}預期將為\s*{_CN_DATE_CAP}",
        re.I,
    ),
    re.compile(
        rf"将于\s*{_CN_DATE_CAP}.{{0,30}}?在联交所开始买卖",
        re.I | re.S,
    ),
    re.compile(
        rf"將於\s*{_CN_DATE_CAP}.{{0,30}}?在聯交所開始買賣",
        re.I | re.S,
    ),
    re.compile(
        rf"{_CN_DATE_CAP}.{{0,30}}?在聯交所開始買賣",
        re.I | re.S,
    ),
    # 定義：「上市日期」指…開始買賣的日期，預期為2026年6月30日
    re.compile(
        rf"開始買\s*賣的日期[，,\s]{{0,10}}(?:預期將為|預期為|為)\s*{_CN_DATE_CAP}",
        re.I,
    ),
    re.compile(
        rf"「上市日期」.{{0,80}}?預期為\s*{_CN_DATE_CAP}",
        re.I | re.S,
    ),
    re.compile(
        rf"「上市日期」.{{0,80}}?预计于\s*{_CN_DATE_CAP}",
        re.I | re.S,
    ),
    re.compile(
        rf"預期於\s*{_CN_DATE_CAP}.{{0,20}}?開始在香港聯交所買賣",
        re.I | re.S,
    ),
    re.compile(
        rf"開始買賣.{{0,40}}?預期\s*(?:H股|股份)?\s*將於\s*{_CN_DATE_CAP}",
        re.I | re.S,
    ),
    # 分配結果公告：開始買賣日期 … 2026年6月30日*
    re.compile(
        rf"開始買賣日期\s*(?:\*[^\n]*\n)?(?:[^\n]*\n){{0,8}}?\s*{_CN_DATE_CAP}\s*\*?",
        re.I,
    ),
]


_OFFER_END_PATTERNS = [
    # HKEX canonical: 「截止辦理香港公開發售申請登記」(语序)
    # Allow long dot-leader gap (HKEX tables use lots of '. ' separators)
    re.compile(
        r"截止辦理香港公開發售申請登記[^0-9]{0,200}"
        r"(20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
        re.I,
    ),
    # Variant: 「香港公開發售截止辦理申請登記」
    re.compile(
        r"香港公開發售截止辦理申請登記[^0-9]{0,200}"
        r"(20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
        re.I,
    ),
    re.compile(
        r"截止辦理申請登記[^0-9]{0,200}"
        r"(20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
        re.I,
    ),
    re.compile(
        r"完成電子申請的截止時間[^0-9]{0,200}"
        r"(20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
        re.I,
    ),
    re.compile(
        r"遞交香港公開發售申請截止日期[^0-9]{0,200}"
        r"(20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
        re.I,
    ),
    re.compile(
        r"電子申請的截止時間[^0-9]{0,200}"
        r"(20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
        re.I,
    ),
]


_OFFER_START_PATTERNS = [
    # HKEX canonical timetable row: 「香港公開發售開始 ........ 2026年6月30日」
    # The gap can be long due to dot leaders, so allow generous spacing
    re.compile(
        rf"(?:香港)?(?:公开发售|公開發售)(?:的)?(?:开始|開始)[.．…·\.\s\|]{{0,200}}{_CN_DATE_CAP}",
        re.I,
    ),
    re.compile(
        rf"(?:开始|開始)(?:辦理)?(?:香港)?(?:公开发售|公開發售)[.．…·\.\s\|]{{0,200}}{_CN_DATE_CAP}",
        re.I,
    ),
    re.compile(
        rf"(?:公开发售|公開發售).{{0,24}}?(?:开始|開始).{{0,80}}?{_CN_DATE_CAP}",
        re.I | re.S,
    ),
    re.compile(
        rf"(?:开始|開始).{{0,16}}?(?:公开发售|公開發售).{{0,80}}?{_CN_DATE_CAP}",
        re.I | re.S,
    ),
]


_ALLOTMENT_PATTERNS = [
    re.compile(
        rf"(?:公[佥布]配發結果|公[佥布]配发结果|公布配发结果|公布配發結果)"
        rf"[^0-9]{{0,80}}{_CN_DATE_CAP}",
        re.I,
    ),
    # HKEX timetable variant: 「刊登...分配結果...公告」
    re.compile(
        rf"分配結果[^0-9]{{0,80}}{_CN_DATE_CAP}",
        re.I,
    ),
]


_REFUND_PATTERNS = [
    # HKEX canonical: 「寄發退款支票」or timetable-row 「退款支票 ........ 2026年7月13日」
    # Allow long dot-leader gap
    re.compile(
        rf"(?:寄發退款|退回款項|退款支票|資金解凍|资金解冻)"
        rf"[^0-9]{{0,200}}{_CN_DATE_CAP}",
        re.I,
    ),
    # Variant: 「發送網上白表電子自動退款指示╱退款支票」(永康招股书措辞)
    re.compile(
        rf"(?:電子自動退款|电子自动退款|退款指示)"
        rf"[^0-9]{{0,200}}{_CN_DATE_CAP}",
        re.I,
    ),
    # Generic refund mention
    re.compile(
        rf"退款[^0-9]{{0,80}}{_CN_DATE_CAP}",
        re.I,
    ),
]


# ---------------------------------------------------------------------------
# OCR / table-spacing normalisation
# ---------------------------------------------------------------------------


def _normalize_prospectus_text(text: str) -> str:
    """Collapse OCR/table spacing between CJK / date digits so regex can match.

    Examples:
      「開 始 買 賣」 → 「開始買賣」
      「2026 年 6 月 30 日」 → 「2026年6月30日」
      「H 股」 → 「H股」
      「截止辦理香港公開發售申請登記(3)」 → 「截止辦理香港公開發售申請登記」
        (HKEX inserts superscript footnote refs like (1) (2) (3) inline,
         which break otherwise-canonical keyword matching)
    """
    if not text:
        return ""
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=\d)\s+(?=[年月日])", "", text)
    text = re.sub(r"(?<=[年月日])\s+(?=\d)", "", text)
    text = re.sub(r"(?<=H)\s+(?=股)", "", text)
    # Strip inline superscript footnote references (1)/(10) etc. that follow
    # CJK tokens — these break keyword matching mid-sentence.
    text = re.sub(r"(?<=[\u4e00-\u9fff])\(\d{1,2}\)", "", text)
    return text


def _parse_cn_date(s: str) -> Optional[date]:
    """Parse 'YYYY年MM月DD日' or 'YYYY-MM-DD' → date. Returns None on failure."""
    if not s:
        return None
    m = _CN_DATE_RE.search(s)
    if m:
        try:
            return date(int(m["y"]), int(m["m"]), int(m["d"]))
        except ValueError:
            return None
    m = _ISO_DATE_RE.search(s)
    if m:
        try:
            return date(int(m["y"]), int(m["m"]), int(m["d"]))
        except ValueError:
            return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _format_iso(d: Optional[date]) -> str:
    return d.isoformat() if d else ""


# ---------------------------------------------------------------------------
# Prospectus URL resolution (via HKEXnews titleSearchServlet)
# ---------------------------------------------------------------------------


def resolve_prospectus_url(
    titlesearch_endpoint: str,
    stock_code: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[str]:
    """Resolve the most recent Chinese prospectus PDF for a stock_code.

    Looks up the numeric stock ID from the HKEX active/inactive securities
    maps, then queries titleSearchServlet.do for prospectus / PHIP rows.
    """
    code = stock_code.lstrip("0").zfill(5)
    for map_url in (
        "https://www1.hkexnews.hk/ncms/script/eds/activestock_sehk_c.json",
        "https://www1.hkexnews.hk/ncms/script/eds/inactivestock_sehk_c.json",
    ):
        try:
            r = requests.get(map_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            r.raise_for_status()
            mapping = r.json()
        except Exception:  # noqa: BLE001
            continue
        stock_id = _lookup_stock_id(mapping, code)
        if stock_id:
            pdf = _search_title_for_prospectus(titlesearch_endpoint, stock_id, timeout=timeout)
            if pdf:
                return pdf
    return None


def _lookup_stock_id(mapping: Any, code: str) -> Optional[str]:
    if isinstance(mapping, dict):
        for k, v in mapping.items():
            if isinstance(v, dict):
                stock_code = v.get("STOCK_CODE") or v.get("stockCode") or v.get("code")
                lseg = v.get("STOCK_LSEG_ID") or v.get("lsegId") or v.get("stockId")
                if stock_code and str(stock_code).zfill(5) == code and lseg:
                    return str(lseg)
            elif isinstance(v, (str, int)) and str(v).zfill(5) == code:
                return str(k)
    elif isinstance(mapping, list):
        for item in mapping:
            if not isinstance(item, dict):
                continue
            stock_code = item.get("STOCK_CODE") or item.get("stockCode") or item.get("code")
            lseg = item.get("STOCK_LSEG_ID") or item.get("lsegId") or item.get("stockId")
            if stock_code and str(stock_code).zfill(5) == code and lseg:
                return str(lseg)
    return None


def _search_title_for_prospectus(
    titlesearch_endpoint: str,
    stock_id: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[str]:
    payload = {
        "market": "SEHK",
        "stockId": stock_id,
        "searchType": "1",
        "t1code": "-2",
        "t2code": "-2",
        "rowRange": "100",
        "lang": "ZH",
    }
    try:
        resp = requests.post(
            titlesearch_endpoint,
            data=payload,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:  # noqa: BLE001
        return None

    results = (
        data.get("result")
        or data.get("results")
        or data.get("hasBooleanSearch")
        or []
    )
    if not isinstance(results, list):
        return None
    candidates = []
    for r in results:
        if not isinstance(r, dict):
            continue
        title = str(r.get("TITLE") or r.get("title") or "")
        if any(kw in title for kw in ("招股書", "上市文件", "PHIP", "Application Proof", "Post-Hearing")):
            link = r.get("FILE_LINK") or r.get("fileLink") or r.get("url")
            date_str = str(r.get("DATE_TIME") or r.get("NOTICE_DATE") or r.get("DATE") or "")
            if link:
                candidates.append((date_str, link))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    link = candidates[0][1]
    if link.startswith("/"):
        return f"https://www1.hkexnews.hk{link}"
    if link.startswith("http"):
        return link
    return f"https://www1.hkexnews.hk/{link.lstrip('/')}"


def fetch_pdf_bytes(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    resp = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/pdf"},
        timeout=timeout,
        stream=True,
    )
    resp.raise_for_status()
    return resp.content


# ---------------------------------------------------------------------------
# Timetable extraction
# ---------------------------------------------------------------------------


def _scan_with_patterns(text: str, patterns: List[re.Pattern]) -> Optional[date]:
    """Apply each pattern in order; return the first parsed date (sanity-checked)."""
    for pat in patterns:
        m = pat.search(text)
        if not m:
            continue
        d = _parse_cn_date(m.group(1))
        if not d:
            continue
        # Guard against distant contract / forecast years in loose matches
        if abs(d.year - date.today().year) <= 1:
            return d
    return None


def parse_expected_timetable(pdf_bytes: bytes) -> Dict[str, str]:
    """Extract Expected-Timetable dates from a prospectus PDF.

    Returns dict with keys (all ISO YYYY-MM-DD or absent):
      offer_open_date, cash_close_date, allotment_date, refund_date, listing_date
    """
    try:
        import pdfplumber
    except ImportError:
        return {}

    out: Dict[str, str] = {}
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            # Expected timetable typically lives near the cover/summary — pages 1-15.
            # Some prospectuses put it later; scan up to 30 pages and concatenate
            # so multi-page patterns match. We stop early once all 5 dates are found.
            total_pages = len(pdf.pages)
            scan_limit = min(30, total_pages)
            full_text = ""
            for i, page in enumerate(pdf.pages[:scan_limit]):
                full_text += (page.extract_text() or "") + "\n"
                # Try after each page; bail out once we have all 5 dates
                if i >= 3:  # need at least cover+summary pages first
                    text_so_far = _normalize_prospectus_text(full_text)
                    found = sum(1 for pats in (
                        _LISTING_PATTERNS, _OFFER_END_PATTERNS, _OFFER_START_PATTERNS,
                        _ALLOTMENT_PATTERNS, _REFUND_PATTERNS,
                    ) if _scan_with_patterns(text_so_far, pats) is not None)
                    if found == 5:
                        break
    except Exception:  # noqa: BLE001
        return out

    text = _normalize_prospectus_text(full_text)

    listing = _scan_with_patterns(text, _LISTING_PATTERNS)
    if listing:
        out["listing_date"] = _format_iso(listing)

    cash_close = _scan_with_patterns(text, _OFFER_END_PATTERNS)
    if cash_close:
        out["cash_close_date"] = _format_iso(cash_close)

    offer_open = _scan_with_patterns(text, _OFFER_START_PATTERNS)
    if offer_open:
        out["offer_open_date"] = _format_iso(offer_open)

    allotment = _scan_with_patterns(text, _ALLOTMENT_PATTERNS)
    if allotment:
        out["allotment_date"] = _format_iso(allotment)

    refund = _scan_with_patterns(text, _REFUND_PATTERNS)
    if refund:
        out["refund_date"] = _format_iso(refund)

    return out


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _has_full_dates(c: Dict[str, Any]) -> bool:
    return all(
        c.get(k) for k in ("offer_open_date", "cash_close_date", "listing_date")
    )


def _is_pdf_eligible(c: Dict[str, Any]) -> bool:
    """Only parse PDFs for companies in/around offer stage.

    Listed/lapsed companies are stale; pure-filing companies haven't published a
    prospectus yet. The expensive PDF fetch is reserved for status values where a
    prospectus PDF actually exists and is worth parsing.
    """
    status = c.get("status") or ""
    return status in ("in_offer", "hearing", "listed", "filed") and status != "lapsed"


def collect(
    cfg: Dict[str, Any],
    snapshot_dir: Path,
    companies: List[Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str]]:
    """For each company missing offer_open_date / cash_close_date / listing_date,
    fetch its prospectus and parse expected-timetable dates.

    Returns ({stock_code: parsed_dates}, status_dict).
    """
    status: Dict[str, str] = {}
    if not cfg.get("enabled", True):
        status["hkex_pdf"] = "disabled"
        return {}, status

    titlesearch = (
        cfg.get("titlesearch_endpoint")
        or "https://www1.hkexnews.hk/search/titleSearchServlet.do"
    )
    max_per_run = int(cfg.get("max_per_run", 5))

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    out: Dict[str, Dict[str, str]] = {}
    failures: List[str] = []

    # Rank candidates: in_offer first, then hearing, then by missing date count
    def _rank_key(c: Dict[str, Any]) -> tuple:
        status = c.get("status") or ""
        # Lower tuple sorts first
        status_rank = (
            0 if status == "in_offer"
            else 1 if status == "hearing"
            else 2 if status == "filed"
            else 3
        )
        # Count how many of the 3 critical dates are missing
        missing = sum(
            1 for k in ("offer_open_date", "cash_close_date", "listing_date")
            if not c.get(k)
        )
        # Prefer companies with a known prospectus URL (no titleSearch needed)
        has_url = 0 if c.get("prospectus_url") else 1
        return (status_rank, -missing, has_url)

    candidates = [
        c for c in companies
        if c.get("stock_code") and not _has_full_dates(c) and _is_pdf_eligible(c)
    ]
    candidates.sort(key=_rank_key)
    candidates = candidates[:max_per_run]

    for c in candidates:
        code = c["stock_code"]
        try:
            url = c.get("prospectus_url") or resolve_prospectus_url(titlesearch, code)
            if not url:
                failures.append(f"{code}:no_url")
                continue
            pdf_bytes = fetch_pdf_bytes(url)
            (snapshot_dir / f"prospectus_{code}.pdf").write_bytes(pdf_bytes)
            dates = parse_expected_timetable(pdf_bytes)
            if dates:
                dates["prospectus_url"] = url
                out[code] = dates
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{code}:{type(exc).__name__}")

    if failures and not out:
        status["hkex_pdf"] = f"degraded:{len(failures)}"
    elif failures:
        status["hkex_pdf"] = f"partial:{len(failures)}/{len(candidates)}"
    else:
        status["hkex_pdf"] = "ok" if candidates else "ok:nothing_to_do"
    return out, status
