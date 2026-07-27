# -*- coding: utf-8 -*-
"""Build grounded international-news card from BHT + AA TOP STORIES (deduped)."""
from __future__ import annotations

import re
from typing import Iterable


# Prefer geopolitics / macro / external markets; skip pure BIST close reprints
_SKIP = re.compile(
    r"BIST\s*100|ENDEKSİ GÜNÜ|halka arz|Masfen|CXMT|Alman şirketler|"
    r"GÖRÜNTÜ DESTEĞİ|WARSH HARİKA|TÜRKİYE ÇOK İYİ|SAVAŞ BİTTİĞİ AN|"
    r"\bSPORTS?\b|football|tennis|NBA",
    re.I,
)
_PRIORITY = [
    re.compile(
        r"saldırıları durdurma|Husilerden Suudi|Suudi petrol|müzakere yok|"
        r"Iran war|Iran\b|Houthi|Saudi.*oil|ceasefire|escalation",
        re.I,
    ),
    re.compile(
        r"NASDAQ|ENFLASYON RAPORU|FAİZLER DÜŞÜRÜLMELİ|gümrük tarifelerini|"
        r"Fed|inflation|tariff|interest rate",
        re.I,
    ),
    re.compile(
        r"İRAN|IRAN|Trump|ABD|OPEC|petrol|altın|tehlike sinyali|"
        r"Ukraine|China|NATO|oil|gold",
        re.I,
    ),
]

_TOPIC_KEYS = [
    "iran",
    "trump",
    "saudi",
    "houthi",
    "husi",
    "nasdaq",
    "fed",
    "inflation",
    "tariff",
    "ukraine",
    "russia",
    "china",
    "oil",
    "brent",
    "milei",
    "brazil",
    "argentina",
    "gaza",
    "israel",
]


def _title(item) -> str:
    if isinstance(item, dict):
        return (item.get("title") or item.get("text") or "").strip()
    return str(item or "").strip()


def _rank(title: str) -> int:
    if not title or _SKIP.search(title):
        return 99
    for i, pat in enumerate(_PRIORITY):
        if pat.search(title):
            return i
    return 50


def _fingerprint(text: str) -> frozenset[str]:
    low = (text or "").replace("İ", "i").replace("I", "i").lower()
    for a, b in (("ı", "i"), ("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ö", "o"), ("ç", "c")):
        low = low.replace(a, b)
    hits = {k for k in _TOPIC_KEYS if k in low}
    if hits:
        return frozenset(hits)
    toks = re.findall(r"[a-z0-9]{4,}", low)
    return frozenset(toks[:8])


def _overlaps(a: frozenset[str], b: frozenset[str]) -> bool:
    if not a or not b:
        return False
    inter = a & b
    if len(inter) >= 2:
        return True
    # single strong topic collision
    strong = {"iran", "trump", "saudi", "houthi", "husi", "nasdaq"}
    return bool(inter & strong)


# Lightweight title→CN cues (TR + EN)
_CN_MAP = [
    (
        re.compile(r"İRAN'?A YÖNELİK SALDIRILARI DURDURMA|saldırıları durdurma|"
                   r"restraint in Iran|avoid a major escalation.*Iran", re.I),
        "美方高层讨论对伊军事升级取舍，释放克制与暂停行动相关信号。",
    ),
    (
        re.compile(r"halihazırda müzakere yok|müzakere yok", re.I),
        "伊方表态当前与美方并无实质谈判。",
    ),
    (
        re.compile(r"Husilerden Suudi|Suudi petrol|Houthi.*Saudi|Saudi.*oil", re.I),
        "胡塞武装袭击沙特石油设施，地缘溢价再度升温。",
    ),
    (
        re.compile(r"NASDAQ 100", re.I),
        "纳斯达克100下跌并创下近阶段新低，外围风险偏好承压。",
    ),
    (
        re.compile(r"ENFLASYON RAPORU|MALİYETLER HIZLA|ideal.*inflation", re.I),
        "美方称读到理想通胀数据、成本快速下降，并继续施压降息。",
    ),
    (
        re.compile(r"FAİZLER DÜŞÜRÜLMELİ|en düşük faiz", re.I),
        "美方呼吁进一步降息，称利率应贴近全球最低水平。",
    ),
    (
        re.compile(r"anlaşma yapma şansımız|İYİ ŞEYLER OLABİLİR", re.I),
        "美方称与伊朗仍有达成协议可能。",
    ),
    (
        re.compile(r"tehlike sinyali", re.I),
        "美股出现风险信号，外部市场情绪偏谨慎。",
    ),
    (
        re.compile(r"gümrük tarifelerini yüzde 20|tariff", re.I),
        "中美关税/贸易限制相关表态继续扰动外围风险偏好。",
    ),
    (
        re.compile(r"Brazil recalls ambassador|Milei", re.I),
        "巴西因米莱言论召回驻阿根廷大使，拉美外交摩擦升温。",
    ),
    (
        re.compile(r"İRAN'A YÖNELİK SALDIRILARI DURDURMA|"
                   r"saldırıları durdurma kararı|attacks on Iran", re.I),
        "美方宣布暂停对伊朗军事行动，并称若谈判失败可能恢复军事行动。",
    ),
]


def title_to_cn_line(title: str) -> str:
    for pat, cn in _CN_MAP:
        if pat.search(title):
            return cn
    return f"（素材）{title}"


def _collect_candidates(
    breaking: Iterable,
    featured: Iterable,
    aa_titles: Iterable | None,
) -> list[tuple[int, int, str, str]]:
    """Return list of (rank, unmapped_flag, title, source_tag)."""
    out: list[tuple[int, int, str, str]] = []
    for tag, src in (
        ("bht_breaking", breaking or []),
        ("bht_featured", featured or []),
        ("aa_top_stories", aa_titles or []),
    ):
        for item in src:
            t = _title(item)
            if not t:
                continue
            rank = _rank(t)
            if rank >= 99:
                continue
            unmapped = 0 if not title_to_cn_line(t).startswith("（素材）") else 1
            out.append((rank, unmapped, t, tag))
    return out


def select_news_titles(
    breaking: Iterable,
    featured: Iterable,
    *,
    aa_titles: Iterable | None = None,
    limit: int = 3,
) -> list[tuple[str, str]]:
    """
    Merge BHT + AA titles, dedupe by topic fingerprint, return [(title, source_tag)].
    Interleave BHT / AA so AA TOP STORIES is not starved after dedupe.
    """
    pool = _collect_candidates(breaking, featured, aa_titles)
    pool.sort(key=lambda x: (x[0], x[1], x[2]))
    bht_pool = [x for x in pool if x[3].startswith("bht")]
    aa_pool = [x for x in pool if x[3] == "aa_top_stories"]

    picked: list[tuple[str, str]] = []
    fps: list[frozenset[str]] = []
    seen_exact: set[str] = set()

    def try_add(item: tuple[int, int, str, str]) -> bool:
        _, _, title, tag = item
        key = re.sub(r"\s+", " ", title).upper()
        if key in seen_exact:
            return False
        fp = _fingerprint(title)
        if any(_overlaps(fp, old) for old in fps):
            return False
        seen_exact.add(key)
        fps.append(fp)
        picked.append((title, tag))
        return True

    bi = ai = 0
    # Alternate BHT → AA → BHT → … so both sources appear when non-overlapping
    turn_aa = False
    while len(picked) < limit and (bi < len(bht_pool) or ai < len(aa_pool)):
        if not turn_aa:
            progressed = False
            while bi < len(bht_pool):
                if try_add(bht_pool[bi]):
                    bi += 1
                    progressed = True
                    break
                bi += 1
            if not progressed:
                while ai < len(aa_pool):
                    if try_add(aa_pool[ai]):
                        ai += 1
                        break
                    ai += 1
        else:
            progressed = False
            while ai < len(aa_pool):
                if try_add(aa_pool[ai]):
                    ai += 1
                    progressed = True
                    break
                ai += 1
            if not progressed:
                while bi < len(bht_pool):
                    if try_add(bht_pool[bi]):
                        bi += 1
                        break
                    bi += 1
        turn_aa = not turn_aa

    return picked


def build_international_news_card(
    breaking,
    featured,
    *,
    aa_titles: Iterable | None = None,
    limit: int = 3,
) -> str:
    picked = select_news_titles(
        breaking, featured, aa_titles=aa_titles, limit=limit
    )
    lines = [
        "【国际新闻素材卡｜来源=BHT突发/重点 + AA Morning Briefing TOP STORIES，已综合去重；"
        "【国际新闻】只能复述下列条目，每条独占一行；禁止编造；正文不要写来源名称】"
    ]
    if not picked:
        lines.append("（暂无可用国际/宏观突发标题）")
        return "\n".join(lines)
    for i, (t, tag) in enumerate(picked, 1):
        src = {
            "bht_breaking": "BHT突发",
            "bht_featured": "BHT重点",
            "aa_top_stories": "AA重要资讯",
        }.get(tag, tag)
        lines.append(f"{i}. {title_to_cn_line(t)}")
        lines.append(f"   原题[{src}]：{t}")
    return "\n".join(lines)
