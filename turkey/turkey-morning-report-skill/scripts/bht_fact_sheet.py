# -*- coding: utf-8 -*-
"""BHT fact sheet for morning-report factual sections (stocks / sectors).

FX & commodities use live quotes from fetch_live_quotes.py instead of prior-close BHT.
"""
from __future__ import annotations

import re
from typing import Optional


SECTOR_CN = {
    "ulaştirma": "运输",
    "ulastirma": "运输",
    "bilişim": "信息",
    "bilisim": "信息",
    "ticaret": "商业",
    "kimya petrol plastik": "化工石油塑料",
    "taş toprak": "陶瓷土石",
    "tas toprak": "陶瓷土石",
    "teknoloji": "科技",
}


def _tr_int(token: str) -> Optional[int]:
    raw = token.replace(" ", "").replace(",", "")
    digits = raw.replace(".", "")
    if digits.isdigit():
        return int(digits)
    return None


def _tr_float_price(token: str) -> Optional[float]:
    t = token.strip().replace(" ", "")
    if not t:
        return None
    t = t.rstrip(".")
    if re.fullmatch(r"\d{1,3}(,\d{3})+", t):
        return float(t.replace(",", ""))
    if "," in t and "." in t:
        return float(t.replace(".", "").replace(",", "."))
    if "," in t:
        return float(t.replace(",", "."))
    if t.count(".") >= 2:
        parts = t.split(".")
        if len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
            return float("".join(parts))
        return float("".join(parts[:-1]) + "." + parts[-1])
    if t.count(".") == 1:
        left, right = t.split(".")
        if left.isdigit() and right.isdigit() and len(right) == 3 and len(left) <= 3:
            return float(left + right)
        return float(t)
    if t.isdigit():
        return float(t)
    return None


def _fmt_pts(v: float) -> str:
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def tl_to_yi_str(amount: int) -> str:
    yi = amount / 1e8
    s = f"{yi:.2f}".rstrip("0").rstrip(".")
    return f"{s}亿里拉"


def normalize_bht_text(text: str) -> str:
    if not text:
        return ""

    def repl_tl(m: re.Match) -> str:
        n = _tr_int(m.group(1))
        if n is None:
            return m.group(0)
        return tl_to_yi_str(n)

    out = re.sub(r"(\d{1,3}(?:\.\d{3})+)\s*TL", repl_tl, text, flags=re.I)
    out = re.sub(r"saat\s*\d{1,2}:\d{2}\s*itibariyle\s*", "", out, flags=re.I)
    out = re.sub(r"\d{1,2}:\d{2}\s*itibariyle\s*", "", out, flags=re.I)
    out = re.sub(r"（?\s*18:30\s*）?", "", out)
    out = re.sub(r"\b18:30\b", "", out)
    return out


def _map_sectors(raw: str) -> list[str]:
    parts = re.split(r",| ve | ve,", raw)
    out: list[str] = []
    for p in parts:
        key = (
            p.strip()
            .lower()
            .replace("ı", "i")
            .replace("ş", "s")
            .replace("ç", "c")
            .replace("ğ", "g")
            .replace("ü", "u")
            .replace("ö", "o")
        )
        key = re.sub(r"\s+", " ", key).strip()
        if not key:
            continue
        if key in SECTOR_CN:
            out.append(SECTOR_CN[key])
            continue
        hit = None
        for k, v in SECTOR_CN.items():
            if k in key or key in k:
                hit = v
                break
        out.append(hit or p.strip())
    return out


def build_morning_bht_fact_sheet(closing_text: str) -> str:
    """Chinese fact lines for 【关键个股】【行业板块表现】 from prior-day BHT close."""
    raw = closing_text or ""
    text = normalize_bht_text(raw)
    lines: list[str] = []
    lines.append(
        "【BHT事实卡｜【关键个股】【行业板块表现】只能复述本卡；"
        "【汇市与大宗商品】只用下方「最新报价事实」，不用本卡收盘汇市句；"
        "禁止分析、补涨跌幅、补收盘价；成交额用「亿里拉」。】"
    )

    # index snapshot for 核心观点 only (not a dedicated section)
    lines.append("【昨日收盘指数摘要｜仅供核心观点引用数字】")
    bits: list[str] = []
    m0 = re.search(
        r"yüzde\s*(-?[\d.,]+)\s*değer kaybederek\s*([\d.]+)\s*puanla",
        text,
        re.I,
    )
    if not m0:
        m0 = re.search(
            r"%\s*(-?[\d.,]+)\s*düşüşle\s*([\d.]+)\s*puandan",
            text,
            re.I,
        )
    if not m0:
        # also handle rise
        m0 = re.search(
            r"yüzde\s*([\d.,]+)\s*değer kazanarak\s*([\d.]+)\s*puanla",
            text,
            re.I,
        )
        if m0:
            chg = m0.group(1).replace(",", ".")
            close_v = _tr_float_price(m0.group(2))
            if close_v is not None:
                bits.append(f"BIST 100 收涨 {chg}%")
                bits.append(f"收盘 {_fmt_pts(close_v)} 点")
    elif m0:
        chg = m0.group(1).replace(",", ".").lstrip("+")
        close_v = _tr_float_price(m0.group(2))
        if close_v is not None:
            chg_disp = chg[1:] if chg.startswith("-") else chg
            bits.append(f"BIST 100 收跌 {chg_disp}%")
            bits.append(f"收盘 {_fmt_pts(close_v)} 点")
    high_m = re.search(r"en yüksek\s*([\d.,]+)\s*puan", text, re.I)
    low_m = re.search(r"en düşük\s*([\d.,]+)\s*puan", text, re.I)
    if high_m:
        hv = _tr_float_price(high_m.group(1))
        if hv is not None:
            bits.append(f"最高 {_fmt_pts(hv)} 点")
    if low_m:
        lv = _tr_float_price(low_m.group(1))
        if lv is not None:
            bits.append(f"最低 {_fmt_pts(lv)} 点")
    lines.append("；".join(bits) + "。" if bits else "（未解析到指数）")

    lines.append("【关键个股事实】")
    vols = re.findall(r"\b([A-Z]{3,6})\s*\((\d{1,3}(?:\.\d{3})+)\s*TL\)", raw)
    if vols:
        parts = []
        for code, num in vols[:5]:
            n = _tr_int(num)
            if n is not None:
                parts.append(f"{code} {tl_to_yi_str(n)}")
        if parts:
            lines.append("成交额前三：" + "，".join(parts[:3]) + "。")
    gain = re.search(
        r"En çok artan hisseler\s+([A-Za-z0-9_,\s]+?)\s+olurken",
        text,
        re.I,
    )
    lose = re.search(
        r"en çok azalan hisseler\s+([A-Za-z0-9_,\s]+?)\s+olarak",
        text,
        re.I,
    )

    def _codes(blob: str) -> str:
        return "、".join(x.strip().upper() for x in blob.split(",") if x.strip())

    if gain:
        lines.append(f"涨幅居前：{_codes(gain.group(1))}。")
    if lose:
        lines.append(f"跌幅居前：{_codes(lose.group(1))}。")

    lines.append("【行业板块表现事实】")
    sec = re.search(
        r"sektörel bazda\s+(.+?)\s+sektörleri yükselirken,\s+(.+?)\s+(?:hisseleri\s+)?en çok düşüş",
        text,
        re.I | re.S,
    )
    if sec:
        lines.append("上涨板块：" + "、".join(_map_sectors(sec.group(1))) + "。")
        lines.append("跌幅居前板块：" + "、".join(_map_sectors(sec.group(2))) + "。")

    return "\n".join(lines)


def format_closing_for_morning_prompt(closing_text: str, live_fact_cn: str = "") -> str:
    """Closing text + BHT stock/sector card + live FX/commodity card."""
    raw = closing_text or ""
    normalized = normalize_bht_text(raw)
    sheet = build_morning_bht_fact_sheet(raw)
    blocks = [
        "【前一交易日收盘数据｜已换算亿里拉、已去掉钟点】",
        normalized,
        "",
        sheet,
    ]
    if live_fact_cn:
        blocks.extend(["", live_fact_cn])
    return "\n".join(blocks)
