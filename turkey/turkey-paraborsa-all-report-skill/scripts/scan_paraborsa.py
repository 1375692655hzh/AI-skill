#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Discover all Paraborsa commentary posts for a target date."""
from __future__ import annotations

import re
import time
from datetime import date
from typing import Iterable

import requests

BASE = "https://www.paraborsa.net"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Known broker slugs for REST slug probing (supplements WP search).
BROKER_SLUGS = [
    "a1-capital", "ahlatci-yatirim", "alnus-yatirim", "anadolu-yatirim", "ata-yatirim",
    "bizim-menkul", "bulls-yatirim", "deniz-yatirim", "destek-yatirim", "gedik-yatirim",
    "garanti-bbva-yatirim", "global-menkul", "halk-yatirim", "hsbc-yatirim", "icbc-yatirim",
    "info-yatirim", "integral-yatirim", "isyatirim", "marbas-menkul", "meksa-yatirim",
    "ncm-investment", "nurol-yatirim", "osmanli-yatirim", "oyak-yatirim", "phillip-capital",
    "qnb-yatirim", "seker-yatirim", "sentiment-algo", "tacirler-yatirim", "turkish-bank",
    "unlu-yatirim", "vakif-yatirim", "yatirim-finansman", "ziraat-yatirim", "colendi-yatirim",
    "acar-yatirim", "allbatross-yatirim", "btcturk-yatirim",
]

DEFAULT_PREFIXES = ["borsa-yorumu", "gun-ici-borsa-yorumu", "viop-yorumu", "haftalik-borsa-yorumu"]


def date_token(d: date) -> str:
    return f"{d.day}-{d.month:02d}-{d.year}"


def dot_date(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").replace("&#8211;", "–").strip()


def matches_target(title: str, slug: str, target: date, *, include_period: bool = True) -> bool:
    dot = dot_date(target)
    token = date_token(target)
    text = f"{title} {slug}"
    if dot in text or token in slug:
        return True
    if include_period and re.search(
        rf"{re.escape(dot)}\s*[-–/]\s*\d{{1,2}}\.{target.month:02d}\.{target.year}",
        title,
    ):
        return True
    return False


def is_commentary(title: str, slug: str, allowed_prefixes: Iterable[str]) -> bool:
    slug_l = slug.lower()
    if any(slug_l.startswith(p + "-") for p in allowed_prefixes):
        return True
    t = (title + " " + slug).lower()
    return any(k in t for k in ("borsa yorumu", "viop yorumu", "gun ici", "haftalik"))


def article_type_from_slug(slug: str) -> str:
    for prefix in DEFAULT_PREFIXES:
        if slug.startswith(prefix + "-"):
            return prefix
    return "other"


def broker_from_slug(slug: str) -> str:
    token = date_token(date.today())  # placeholder replaced below
    return slug


def parse_broker_slug(slug: str, target: date) -> str:
    token = date_token(target)
    for prefix in DEFAULT_PREFIXES:
        needle = f"{prefix}-"
        if slug.startswith(needle) and slug.endswith(f"-{token}"):
            return slug[len(needle): -len(token) - 1]
    return slug


def wp_search(target: date, *, delay: float = 0.8) -> dict[str, dict]:
    found: dict[str, dict] = {}
    queries = [dot_date(target), date_token(target), "borsa yorumu", f"borsa-yorumu {dot_date(target)}"]
    for q in queries:
        try:
            resp = requests.get(
                f"{BASE}/wp-json/wp/v2/posts",
                params={"search": q, "per_page": 100},
                headers=HEADERS,
                timeout=30,
            )
            if resp.status_code != 200:
                continue
            for post in resp.json():
                slug = post.get("slug", "")
                if not slug or slug in found:
                    continue
                title = strip_html(post.get("title", {}).get("rendered", ""))
                found[slug] = {
                    "slug": slug,
                    "title": title,
                    "url": post.get("link", ""),
                    "article_type": article_type_from_slug(slug),
                    "broker_slug": parse_broker_slug(slug, target),
                    "discovered_via": f"search:{q}",
                }
            time.sleep(delay)
        except requests.RequestException:
            continue
    return found


def slug_probe(
    target: date,
    *,
    prefixes: Iterable[str] = DEFAULT_PREFIXES,
    brokers: Iterable[str] = BROKER_SLUGS,
    delay: float = 0.35,
) -> dict[str, dict]:
    found: dict[str, dict] = {}
    token = date_token(target)
    for prefix in prefixes:
        for broker in brokers:
            slug = f"{prefix}-{broker}-{token}"
            try:
                resp = requests.get(
                    f"{BASE}/wp-json/wp/v2/posts",
                    params={"slug": slug},
                    headers=HEADERS,
                    timeout=20,
                )
                if resp.status_code == 200 and resp.json():
                    post = resp.json()[0]
                    title = strip_html(post.get("title", {}).get("rendered", ""))
                    found[slug] = {
                        "slug": slug,
                        "title": title,
                        "url": post.get("link", ""),
                        "article_type": prefix,
                        "broker_slug": broker,
                        "discovered_via": "slug_probe",
                    }
                time.sleep(delay)
            except requests.RequestException:
                continue
    return found


def scan_all(
    target: date,
    *,
    allowed_prefixes: Iterable[str] | None = None,
    include_period_ranges: bool = True,
    search_delay: float = 0.8,
    probe_delay: float = 0.35,
) -> list[dict]:
    prefixes = list(allowed_prefixes or DEFAULT_PREFIXES)
    merged = {**wp_search(target, delay=search_delay), **slug_probe(target, prefixes=prefixes, delay=probe_delay)}
    articles = [
        it for it in merged.values()
        if is_commentary(it["title"], it["slug"], prefixes)
        and matches_target(it["title"], it["slug"], target, include_period=include_period_ranges)
    ]
    articles.sort(key=lambda x: (x["article_type"], x["broker_slug"], x["slug"]))
    return articles
