# -*- coding: utf-8 -*-
"""Build grounded international-news card from BHT + AA TOP STORIES.

Design principle: each qualifying headline = one independent news item.
No merging, no synthesis, no rewriting, no direction fabrication.

Selection pipeline (Plan C: rule prefilter + LLM index picker fallback):
  1. _SKIP category filter (drop non-international: BIST close, sports,
     purely domestic TR firms/people, clickbait).
  2. Same-entity spam cap (if the same person/company appears in >=3
     headlines, keep only the first 2 — protects against one speaker
     flooding the wire with related quotes).
  3. Exact-string dedup (same headline from two sources).
  4. If still > MAX_ITEMS (default 10), one cheap LLM call returns a JSON
     list of 1-based indices to keep, ranked by importance. LLM never
     touches the title text, so zero fabrication risk. Any malformed
     response falls back to taking the first MAX_ITEMS in source order.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Iterable, Optional


# Hard cap on the number of items shown in the final card.
MAX_ITEMS = 10
# Cap on consecutive headlines mentioning the same entity (person/company).
# Kicks in only for true floods (>=3 mentions of the same speaker/firm) so a
# normal "Trump said X" + "Trump said Y" pair is preserved.
_SAME_ENTITY_KEEP = 2
_SAME_ENTITY_TRIGGER = 3


# Category filter — these are NOT international news, drop entirely.
_SKIP = re.compile(
    r"BIST\s*100|ENDEKSİ GÜNÜ|halka arz|Masfen|CXMT|Alman şirketler|"
    r"GÖRÜNTÜ DESTEĞİ|WARSH HARİKA|TÜRKİYE ÇOK İYİ|SAVAŞ BİTTİĞİ AN|"
    r"\bSPORTS?\b|football|tennis|NBA|"
    # purely domestic non-market items: currency/gas price checkers, clickbait
    r"Dolar ne kadar oldu|Motorin|ne kadar oldu|son durum ne|"
    r"latest price|latest situation",
    re.I,
)


def _title(item) -> str:
    if isinstance(item, dict):
        return (item.get("title") or item.get("text") or "").strip()
    return str(item or "").strip()


def _entity_key(title: str) -> Optional[str]:
    """Best-effort entity extraction for spam-cap. Returns a normalized key
    identifying the main subject (person / company / country), or None.

    Used ONLY to detect the same speaker/firm flooding the wire (e.g. a
    minister giving 4 quotes in a row). Not used for topic dedup.

    Handles common Turkish headline patterns:
      - "BAKAN ŞİMŞEK: ..."        → "şimşek"
      - "Şimşek'ten ..."            → "şimşek"
      - "EXXON'UN ..."              → "exxon"
      - "Yapı Kredi ..."            → "yapi kredi"
      - "Trump announces ..."       → "trump"
    """
    if not title:
        return None
    # Strip leading timestamp / source tags / noise prefixes
    t = re.sub(r"^[\d\s:.\-]+", "", title).strip()
    # Drop leading title words that precede a person's name
    t = re.sub(
        r"^(?:BAKAN|BAŞKAN|BAŞBAKAN|CUMHURBAŞKANI|Hazine ve Maliye Bakanı|"
        r"Merkez Bankası Başkanı| Başkan)\s+",
        "",
        t,
        flags=re.I,
    )

    # Match leading capitalized run (Latin + Turkish letters + apostrophe
    # for possessive suffixes). Stop at apostrophe-suffix when extracting
    # the person/firm name core.
    m = re.match(
        r"([A-ZÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ']+(?:\s+[A-ZÇĞİÖŞÜ][a-zA-ZçğıöşüÇĞİÖŞÜ']+){0,3})",
        t,
    )
    if not m:
        return None
    phrase = m.group(1).strip()
    # Strip Turkish possessive suffixes attached via apostrophe:
    #   "Şimşek'ten" → "şimşek", "EXXON'UN" → "exxon", "Apple'ın" → "apple"
    phrase = re.split(r"['’]", phrase)[0]
    phrase = phrase.strip()
    if not phrase:
        return None

    # Normalize TR lower for matching
    key = phrase.lower()
    for a, b in (("ı", "i"), ("ş", "s"), ("ğ", "g"), ("ü", "u"),
                 ("ö", "o"), ("ç", "c"), ("İ", "i")):
        key = key.replace(a, b)
    # Stop-word entities too generic to be useful (would over-cap)
    if key in {"abd", "irak", "iran", "euro", "bakan"}:
        return None
    return key


def _collect_candidates(
    breaking: Iterable,
    featured: Iterable,
    aa_titles: Iterable | None,
) -> list[tuple[str, str]]:
    """Return list of (title, source_tag) in source order."""
    out: list[tuple[str, str]] = []
    for tag, src in (
        ("bht_breaking", breaking or []),
        ("bht_featured", featured or []),
        ("aa_top_stories", aa_titles or []),
    ):
        for item in src:
            t = _title(item)
            if not t:
                continue
            out.append((t, tag))
    return out


def _prefilter(
    candidates: list[tuple[str, str]],
    *,
    limit: int = 0,
) -> list[tuple[str, str]]:
    """Apply _SKIP, same-entity cap, exact dedup. Return kept items in order."""
    picked: list[tuple[str, str]] = []
    seen_exact: set[str] = set()
    entity_counts: dict[str, int] = {}

    for title, tag in candidates:
        if _SKIP.search(title):
            continue
        key = re.sub(r"\s+", " ", title).upper()
        if key in seen_exact:
            continue
        seen_exact.add(key)

        # Same-entity spam cap: if this entity already has >=_SAME_ENTITY_KEEP
        # items AND total occurrences (including this one) reach the trigger
        # threshold, drop. This only kicks in for true floods (>=3 mentions),
        # so a normal "Trump said X" + "Trump said Y" pair is preserved.
        ent = _entity_key(title)
        if ent:
            cnt = entity_counts.get(ent, 0) + 1
            entity_counts[ent] = cnt
            if cnt > _SAME_ENTITY_KEEP and cnt >= _SAME_ENTITY_TRIGGER:
                continue

        picked.append((title, tag))
        if limit and len(picked) >= limit:
            break
    return picked


# ---------------------------------------------------------------------------
# LLM index picker (only triggered when prefilter still returns > MAX_ITEMS)
# ---------------------------------------------------------------------------

_IMPORTANCE_CRITERIA = """这是「土耳其股市早报」的国际新闻选取。重要性按"对土耳其/伊斯坦布尔资本市场的外溢影响"排序，不是泛全球财经重要性。

【第一档 — 必选，对土耳其直接相关】
- 土耳其本土：土耳其公司/银行/部委动态、土耳其宏观数据（贸易差额/CPI/PMI/就业/外资流动）、里拉与 TL 资产相关
- 中东地缘（土耳其邻区）：以色列-哈马斯/加沙、伊拉克、叙利亚、伊朗、沙特、东地中海——这些直接扰动土耳其 EM 风险偏好与外资流向

【第二档 — 应选，会传导到土耳其】
- 主要央行动态（Fed/ECB/BOJ 利率与表态）→ 影响全球流动性、套利交易、里拉汇率
- 欧元区宏观（CPI/GDP/PMI）→ ECB 路径 → 欧元/里拉
- 全球风险偏好信号：股指期货齐涨跌、套利交易持仓、恐慌指数
- 大宗商品（油价/金价）异动 → 土耳其通胀与经常账户

【剔除 — 即使头条再大也不选】
- 单一美股/欧股个股财报（Apple/Exxon/Microsoft/Nvidia 等都不要——土耳其投资者不关心海外个股 EPS）
- 单一他国公司并购/股权变动（除非涉及土耳其主体）
- 他国纯国内政治无区域外溢（如德国内政、美国国内立法、韩国国内事务）
- 与已选条目主题重复的次级新闻（如同主题的月率+年率，只留年率）
- 标题党/无具体数据的泛泛句（如"风险信号升温"无数字）"""


_LLM_PROMPT_TEMPLATE = """你是土耳其股市早报的新闻编辑。下面是 {n} 条今日原题（来自 BHT 突发/重点 + AA TOP STORIES）。

请选出**最多 {max_items} 条**最相关于土耳其股市 / 伊斯坦布尔资本市场 / 中东地缘外溢的新闻，返回严格的 JSON：一个 1-based 序号数组，按相关性从高到低排列。

{_IMPORTANCE_CRITERIA}

铁律：
- 只能从下面列表的序号中选，不得编造序号
- 不得改写、合并、翻译任何标题
- 不得返回序号数组以外的任何文字（不要解释、不要前言）
- 数组长度必须 <= {max_items}
- 宁缺毋滥：如果相关新闻不够 {max_items} 条，就少返回；不要为了凑数填美股财报或他国内政

原题列表：
{items}

JSON 输出（仅数组，不要 ```json 代码块标记）："""


def _llm_pick_indices(
    items: list[tuple[str, str]],
    max_items: int,
    *,
    llm_cfg: dict | None,
) -> Optional[list[int]]:
    """Call LLM to pick <=max_items indices (1-based). Returns None on any error."""
    if not llm_cfg:
        return None
    try:
        import call_llm  # local module in scripts/
    except ImportError:
        return None

    numbered = "\n".join(f"{i+1}. [{tag}] {t}" for i, (t, tag) in enumerate(items))
    prompt = _LLM_PROMPT_TEMPLATE.format(
        n=len(items),
        max_items=max_items,
        items=numbered,
        _IMPORTANCE_CRITERIA=_IMPORTANCE_CRITERIA,
    )
    try:
        resp = call_llm.call_llm(
            prompt,
            provider=llm_cfg["provider"],
            model=llm_cfg["model"],
            api_key_env=llm_cfg["api_key_env"],
            base_url=llm_cfg.get("base_url"),
            temperature=0.0,  # deterministic ranking
            max_tokens=400,  # JSON index list, short
        )
    except Exception as e:
        print(f"[news_filter] LLM call failed: {e}", file=sys.stderr)
        return None
    if not resp:
        return None

    # Extract the first JSON array in the response (lenient: tolerate
    # accidental code fences / surrounding prose, but the prompt asks for
    # bare array so the common case is a clean parse).
    resp = resp.strip()
    m = re.search(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]", resp)
    if not m:
        print(f"[news_filter] no JSON array in LLM response: {resp[:120]!r}", file=sys.stderr)
        return None
    nums: list[int] = []
    for tok in re.findall(r"\d+", m.group(1)):
        idx = int(tok)
        # 1-based, must be in valid range, no dupes
        if 1 <= idx <= len(items) and idx not in nums:
            nums.append(idx)
        if len(nums) >= max_items:
            break
    if not nums:
        return None
    return nums


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def select_news_titles(
    breaking: Iterable,
    featured: Iterable,
    *,
    aa_titles: Iterable | None = None,
    limit: int = 0,
    max_items: int = MAX_ITEMS,
    llm_cfg: dict | None = None,
) -> list[tuple[str, str]]:
    """
    Return [(title, source_tag)] in source order, after prefilter + optional
    LLM index selection. Result length <= max_items.

    Pipeline:
      1. Rule prefilter (_SKIP category filter + same-entity flood cap +
         exact-string dedup).
      2. If still > cap, one cheap LLM call ranks ALL remaining items by
         relevance to Turkish equities / Istanbul bourse / Middle-East
         geopolitics and returns the top-N indices. LLM never touches
         title text → zero fabrication risk.
      3. Fallback on any LLM error: take first cap items in source order.

    No fixed Turkey-vs-global ratio — the LLM ranks purely by relevance,
    so the cap (default 10) is a ceiling, not a target. Fewer items is OK.

    - limit<=0 means "use max_items as the soft cap". limit>0 overrides
      max_items (kept for backward compat).
    """
    cap = limit if limit > 0 else max_items
    candidates = _collect_candidates(breaking, featured, aa_titles)
    filtered = _prefilter(candidates, limit=0)  # no hard cut yet

    if len(filtered) <= cap:
        return filtered[:cap] if cap else filtered

    # Too many items — let the LLM rank by relevance to Turkey and pick top N.
    # No tiered force-keep: the prompt asks the LLM to judge "relevance to
    # Turkish equities / Istanbul bourse / Middle East geopolitics" as a
    # single axis, which naturally surfaces both Turkey-local and
    # spillover (Fed/ECB/euro CPI/carry trade) items while suppressing
    # irrelevant global news (US single-stock earnings, other-country
    # domestic politics). On any LLM error, fall back to first N in source
    # order (deterministic, no fabrication).
    picked_idxs = _llm_pick_indices(filtered, cap, llm_cfg=llm_cfg)
    if picked_idxs:
        return [filtered[i - 1] for i in picked_idxs if 1 <= i <= len(filtered)]

    print(
        f"[news_filter] LLM picker unavailable/invalid; "
        f"falling back to first {cap} of {len(filtered)} items.",
        file=sys.stderr,
    )
    return filtered[:cap]


def build_international_news_card(
    breaking,
    featured,
    *,
    aa_titles: Iterable | None = None,
    limit: int = 0,
    max_items: int = MAX_ITEMS,
    llm_cfg: dict | None = None,
) -> str:
    picked = select_news_titles(
        breaking,
        featured,
        aa_titles=aa_titles,
        limit=limit,
        max_items=max_items,
        llm_cfg=llm_cfg,
    )
    lines = [
        "【国际新闻素材卡｜仅限今日(TR) BHT突发/重点 + 今日 AA TOP STORIES；"
        "禁止使用非今日突发/旧稿；【国际新闻】把下列每条原题逐条翻译成中文，"
        "每条独占一行；一条原题 = 一条新闻，禁止合并多条、禁止编造原题没有的数字或方向；"
        "原题里的涨跌幅/百分比/方向词必须忠实保留；正文不要写来源名称】"
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
        lines.append(f"{i}. 原题[{src}]：{t}")
    return "\n".join(lines)
