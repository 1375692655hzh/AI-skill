#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BloombergHT closing review fetcher — aligned with Turkey-investment/piyasa_ozesi.py."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.bloomberght.com"
FALLBACK_URL = f"{BASE}/borsa"
LIST_PAGE_URL = f"{BASE}/tum-piyasa-haberleri"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

TITLE_RE = re.compile(
    r"(piyasa\s*özeti|piyasalarda\s*günün\s*özeti)\s*:", re.IGNORECASE
)

_TR_MONTHS = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4,
    "mayıs": 5, "mayis": 5, "haziran": 6, "temmuz": 7, "ağustos": 8,
    "agustos": 8, "eylül": 9, "eylul": 9, "ekim": 10, "kasım": 11,
    "kasim": 11, "aralık": 12, "aralik": 12,
}

RSS_LAG_BUFFER = 100
MIN_RECENT_SCAN = 80
FINAL_FALLBACK_SCAN = 200


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def parse_tr_date_from_title(title: str) -> Optional[date]:
    m = re.search(r"(\d{1,2})\s+(\S+)\s+(\d{4})", title)
    if not m:
        return None
    month = _TR_MONTHS.get(m.group(2).lower())
    if not month:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None


def _failure(target_date: date, error: str, method: str | None = None) -> dict:
    payload = {
        "ok": False,
        "target_date": target_date.isoformat(),
        "error": error,
        "title": None,
        "url": None,
        "text": None,
        "source": "bloomberght",
        "fallback_url": FALLBACK_URL,
    }
    if method:
        payload["fetch_method"] = method
    return payload


def _success(
    target_date: date,
    title: str,
    url: str,
    text: str,
    method: str,
    article_id: int | None = None,
) -> dict:
    payload = {
        "ok": True,
        "target_date": target_date.isoformat(),
        "title": title,
        "url": url,
        "text": text,
        "source": "bloomberght",
        "error": None,
        "fetch_method": method,
    }
    if article_id:
        payload["article_id"] = article_id
    return payload


def extract_article_text(url: str, html: str | None = None) -> str:
    try:
        if html is None:
            resp = requests.get(url, timeout=20, headers=HEADERS)
            resp.raise_for_status()
            html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        body = (
            soup.select_one("div.news-content")
            or soup.select_one("div.article-body")
            or soup.find("article")
            or soup
        )
        seen: set[str] = set()
        parts: list[str] = []
        for el in body.find_all(["h2", "h3", "p"], recursive=True):
            txt = el.get_text(" ", strip=True)
            if txt and len(txt) > 15 and txt not in seen:
                seen.add(txt)
                parts.append(txt)
        return "\n".join(parts)
    except Exception as e:
        return f"ERROR extracting article: {e}"


def _lookup_manifest(workdir: Path | None, target_date: date) -> Optional[dict]:
    if not workdir:
        return None
    date_iso = target_date.isoformat()
    manifest = (
        workdir / "reports" / "turkey-market-reports" / date_iso / f"{date_iso}_manifest.json"
    )
    if not manifest.is_file():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return None
    for entry in data.get("files", []):
        if (
            entry.get("source") == "bloomberght"
            and entry.get("position") == "closing_detail"
            and entry.get("status") == "ok"
        ):
            file_path = entry.get("file_path")
            if not file_path:
                continue
            fp = Path(file_path)
            if not fp.is_absolute():
                fp = workdir / fp
            if fp.is_file():
                text = fp.read_text(encoding="utf-8")
                return _success(
                    target_date,
                    title=entry.get("title") or fp.stem,
                    url=entry.get("url") or "",
                    text=text,
                    method="manifest",
                    article_id=entry.get("article_id"),
                )
    return None


def _find_in_list_page(target_date: date, list_url: str = LIST_PAGE_URL) -> Optional[dict]:
    try:
        resp = requests.get(list_url, timeout=20, headers=HEADERS)
        resp.raise_for_status()
    except requests.RequestException as e:
        log(f"List page fetch failed: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    for link in soup.find_all("a", href=True):
        title = link.get_text(" ", strip=True)
        if not title or not TITLE_RE.search(title):
            continue
        art_date = parse_tr_date_from_title(title)
        if art_date != target_date:
            continue
        href = urljoin(BASE, link["href"])
        article_id = None
        m = re.search(r"-(\d{6,})(?:[/?#]|$)", href)
        if m:
            article_id = int(m.group(1))
        clean_title = title.split("|")[0].strip()
        title_match = re.match(
            r"((?:Piyasalarda günün özeti|Piyasa özeti):[^.]+(?:fiyatları|son durum))",
            clean_title,
            re.IGNORECASE,
        )
        if title_match:
            clean_title = title_match.group(1).strip()
        text = extract_article_text(href)
        return _success(
            target_date,
            title=clean_title,
            url=href,
            text=text,
            method="list_page",
            article_id=article_id,
        )
    return None


def _load_bht_cache(workdir: Path | None, cache_dir: Path) -> dict:
    for base in (workdir, cache_dir):
        if not base:
            continue
        path = base / ".cache" / "bht_id_cache.json"
        if path.is_file():
            try:
                cache = json.loads(path.read_text(encoding="utf-8"))
                cache.setdefault("date_to_id", {})
                cache.setdefault("known_hit_ids", [])
                cache.setdefault("last_max_id", 0)
                return cache
            except Exception:
                pass
    return {"last_max_id": 0, "known_hit_ids": [], "date_to_id": {}}


def _save_bht_cache(cache_dir: Path, cache: dict) -> None:
    path = cache_dir / "bht_id_cache.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _record_date_to_id(cache_dir: Path, cache: dict, date_iso: str, article_id: int) -> None:
    cache.setdefault("date_to_id", {})[date_iso] = article_id
    known = set(cache.get("known_hit_ids", []))
    known.add(article_id)
    cache["known_hit_ids"] = sorted(known, reverse=True)[:50]
    _save_bht_cache(cache_dir, cache)


def fetch_rss_max_id(rss_url: str = f"{BASE}/rss") -> Optional[int]:
    try:
        resp = requests.get(rss_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log(f"RSS max-id fetch failed: {e}")
        return None
    soup = BeautifulSoup(resp.text, "xml")
    max_id = 0
    for link in soup.find_all("link"):
        m = re.search(r"-(\d{6,})$", link.get_text(strip=True))
        if m:
            max_id = max(max_id, int(m.group(1)))
    return max_id or None


def probe_id(article_id: int, retries: int = 2) -> Optional[dict]:
    url = f"{BASE}/x-{article_id}"
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        except requests.RequestException:
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
                continue
            return None
        if resp.status_code in (429, 500, 502, 503, 504):
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
                continue
            return None
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_tag = soup.find("title")
        if not title_tag:
            return None
        title = title_tag.get_text(strip=True)
        if not TITLE_RE.search(title):
            return None
        return {
            "id": article_id,
            "url": resp.url,
            "title": title.split("|")[0].strip(),
            "date": parse_tr_date_from_title(title),
            "html": resp.text,
        }
    return None


def scan_ids(start_id: int, count: int, workers: int = 8) -> list[dict]:
    hits: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(probe_id, start_id - i): start_id - i for i in range(count)}
        for fut in as_completed(futures):
            art = fut.result()
            if art:
                hits.append(art)
    hits.sort(key=lambda a: -a["id"])
    return hits


def _scan_with_cache(
    current_max_id: int,
    cache: dict,
    cache_dir: Path,
    full_scan_count: int = 450,
) -> list[dict]:
    last_max = cache.get("last_max_id", 0)
    known_hit_ids = cache.get("known_hit_ids", [])

    if last_max and current_max_id <= last_max and known_hit_ids:
        hits = scan_ids(current_max_id, MIN_RECENT_SCAN)
        seen = {h["id"] for h in hits}
        for aid in known_hit_ids:
            if aid in seen:
                continue
            art = probe_id(aid)
            if art:
                hits.append(art)
        hits.sort(key=lambda a: -a["id"])
    elif last_max and current_max_id > last_max:
        scan_count = min(current_max_id - last_max + 50, full_scan_count)
        hits = scan_ids(current_max_id, scan_count)
        seen = {h["id"] for h in hits}
        for aid in known_hit_ids:
            if aid in seen:
                continue
            art = probe_id(aid)
            if art:
                hits.append(art)
        hits.sort(key=lambda a: -a["id"])
    else:
        hits = scan_ids(current_max_id, full_scan_count)

    if hits:
        cache["last_max_id"] = max(last_max, current_max_id)
        all_hit_ids = list({h["id"] for h in hits} | set(known_hit_ids))
        cache["known_hit_ids"] = sorted(all_hit_ids, reverse=True)[:50]
        for h in hits:
            if h.get("date"):
                cache.setdefault("date_to_id", {})[h["date"].isoformat()] = h["id"]
        _save_bht_cache(cache_dir, cache)
    return hits


def _find_by_id_scan(
    target_date: date,
    cache_dir: Path,
    workdir: Path | None,
    rss_url: str,
) -> Optional[dict]:
    cache = _load_bht_cache(workdir, cache_dir)
    date_iso = target_date.isoformat()

    cached_id = cache.get("date_to_id", {}).get(date_iso)
    if cached_id:
        log(f"date_to_id cache hit: {date_iso} -> {cached_id}")
        art = probe_id(cached_id)
        if art and art.get("date") == target_date:
            text = extract_article_text(art["url"], art.get("html"))
            return _success(
                target_date,
                title=art["title"],
                url=art["url"],
                text=text,
                method="date_to_id",
                article_id=art["id"],
            )

    upper = fetch_rss_max_id(rss_url)
    if not upper:
        return None
    upper += RSS_LAG_BUFFER
    hits = _scan_with_cache(upper, cache, cache_dir)

    for art in hits:
        if art.get("date") == target_date:
            _record_date_to_id(cache_dir, cache, date_iso, art["id"])
            text = extract_article_text(art["url"], art.get("html"))
            return _success(
                target_date,
                title=art["title"],
                url=art["url"],
                text=text,
                method="id_scan",
                article_id=art["id"],
            )

    latest = max(hits, key=lambda a: a["id"]) if hits else None
    if latest and latest.get("date") and target_date > latest["date"]:
        blind_lo = latest["id"] + 1
        blind_hi = upper
        if 0 < blind_hi - blind_lo + 1 <= 300:
            log(f"Blind-zone slow scan [{blind_lo}, {blind_hi}]")
            for aid in range(blind_hi, blind_lo - 1, -1):
                art = probe_id(aid, retries=3)
                if art and art.get("date") == target_date:
                    _record_date_to_id(cache_dir, cache, date_iso, art["id"])
                    text = extract_article_text(art["url"], art.get("html"))
                    return _success(
                        target_date,
                        title=art["title"],
                        url=art["url"],
                        text=text,
                        method="blind_scan",
                        article_id=art["id"],
                    )
        extra_hits = scan_ids(upper + FINAL_FALLBACK_SCAN, FINAL_FALLBACK_SCAN)
        for art in extra_hits:
            if art.get("date") == target_date:
                _record_date_to_id(cache_dir, cache, date_iso, art["id"])
                text = extract_article_text(art["url"], art.get("html"))
                return _success(
                    target_date,
                    title=art["title"],
                    url=art["url"],
                    text=text,
                    method="extended_scan",
                    article_id=art["id"],
                )
    return None


def _fetch_via_project(workdir: Path, target_date: date) -> Optional[dict]:
    date_iso = target_date.isoformat()
    fetch_py = workdir / "fetch.py"
    piyasa_py = workdir / "piyasa_ozesi.py"

    if fetch_py.is_file():
        cmd = [sys.executable, str(fetch_py), "closing", date_iso, "--json"]
        script_name = "fetch.py closing"
    elif piyasa_py.is_file():
        cmd = [sys.executable, str(piyasa_py), date_iso, "--json", "--quiet"]
        script_name = "piyasa_ozesi.py"
    else:
        return None

    log(f"Delegating to project {script_name} for {date_iso}")
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        log(f"Project fetcher failed: {e}")
        return None

    if proc.returncode != 0 or not proc.stdout.strip():
        if proc.stderr:
            log(proc.stderr.strip()[:300])
        return None

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if not payload.get("ok"):
        return None

    text = payload.get("markdown") or ""
    file_path = payload.get("file_path")
    if not text and file_path:
        fp = Path(file_path)
        if not fp.is_absolute():
            fp = workdir / fp
        if fp.is_file():
            text = fp.read_text(encoding="utf-8")
    if not text:
        return None

    article_id = payload.get("article_id")
    if not article_id and payload.get("url"):
        m = re.search(r"-(\d{6,})(?:[/?#]|$)", payload["url"])
        if m:
            article_id = int(m.group(1))

    return _success(
        target_date,
        title=payload.get("title") or "",
        url=payload.get("url") or "",
        text=text,
        method="project_fetch",
        article_id=article_id,
    )


def fetch_closing_review(
    target_date: date,
    cache_dir: Path,
    *,
    workdir: Path | None = None,
    rss_url: str = f"{BASE}/rss",
    list_page_url: str = LIST_PAGE_URL,
    use_project_fetcher: bool = True,
) -> dict:
    """Fetch BloombergHT closing review using the Turkey-investment fetch chain."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"bloomberght_closing_{target_date.isoformat()}.json"

    if cache_file.is_file():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if cached.get("ok") and cached.get("text"):
                return cached
        except Exception:
            pass

    attempts: list[tuple[str, Optional[dict]]] = []

    manifest = _lookup_manifest(workdir, target_date)
    attempts.append(("manifest", manifest))
    if manifest:
        cache_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest

    list_hit = _find_in_list_page(target_date, list_page_url)
    attempts.append(("list_page", list_hit))
    if list_hit:
        cache_file.write_text(json.dumps(list_hit, ensure_ascii=False, indent=2), encoding="utf-8")
        return list_hit

    if use_project_fetcher and workdir:
        project_hit = _fetch_via_project(workdir, target_date)
        attempts.append(("project_fetch", project_hit))
        if project_hit:
            cache_file.write_text(json.dumps(project_hit, ensure_ascii=False, indent=2), encoding="utf-8")
            return project_hit

    scan_hit = _find_by_id_scan(target_date, cache_dir, workdir, rss_url)
    attempts.append(("id_scan", scan_hit))
    if scan_hit:
        cache_file.write_text(json.dumps(scan_hit, ensure_ascii=False, indent=2), encoding="utf-8")
        return scan_hit

    tried = [name for name, hit in attempts if hit is None]
    result = _failure(
        target_date,
        error=(
            "No matching BloombergHT closing review found. "
            f"Tried: {', '.join(tried)}. "
            "If the article exists, retry later or use fetch.py closing by-id."
        ),
        method="none",
    )
    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
