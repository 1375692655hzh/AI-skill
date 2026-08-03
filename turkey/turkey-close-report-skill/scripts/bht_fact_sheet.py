# -*- coding: utf-8 -*-
"""Build a BHT-only Chinese fact sheet for close-report factual sections."""
from __future__ import annotations

import re
from typing import Optional


# Turkish sector name -> Chinese (BHT wording). Covers all sectors that appear
# in real BHT closing reviews 2026-07-27/28/29 plus common BIST sector labels.
SECTOR_CN = {
    # transport / info / trade
    "ulaştirma": "运输",
    "ulastirma": "运输",
    "iletişim": "通信",
    "iletisim": "通信",
    "bilişim": "信息",
    "bilisim": "信息",
    "teknoloji": "科技",
    "ticaret": "商业",
    # cyclical / chemicals
    "kimya petrol plastik": "化工石油塑料",
    "taş toprak": "陶瓷土石",
    "tas toprak": "陶瓷土石",
    "cam": "玻璃",
    # financials
    "banka": "银行",
    "bankacılık": "银行",
    "bankacilik": "银行",
    "sigorta": "保险",
    "finans": "金融",
    "holding": "控股",
    "gayrimenkul": "房地产",
    # resources / energy
    "madencilik": "矿业",
    "metal ana sanayi": "金属工业",
    "metal esya": "金属制品",
    "demir çelik": "钢铁",
    "elektrik": "电力",
    "enerji": "能源",
    "petrol": "石油",
    # consumer / industrial
    "gıda": "食品",
    "gida": "食品",  # ascii form after ı→i normalization
    "içecek": "饮料",
    "tekstil": "纺织",
    "otomotiv": "汽车",
    "inşaat": "建筑",
    "turizm": "旅游",
    "sağlık": "医疗",
    "sınai": "工业",
    "sanayi": "工业",
    "ormancılık": "林业",
    "orman": "林业",
    "kağıt": "造纸",
    "savunma": "国防",
    # services / misc consumer
    "spor": "体育",
    "medya": "传媒",
    "perakende": "零售",
    "lojistik": "物流",
    "tarım": "农业",
    "balıkçılık": "渔业",
    "tekstil deri": "纺织皮革",
    "deri": "皮革",
    "kamu": "公用事业",
    "hizmet": "服务",
    "demirÇelik": "钢铁",
    "ana sanayi": "工业",
    "esya": "制品",
    "makina": "机械",
}


def _tr_int(token: str) -> Optional[int]:
    """Parse TR/EU integer with '.' thousand separators: 16.555.811.753"""
    raw = token.replace(" ", "").replace(",", "")
    if not re.fullmatch(r"\d+(\.\d{3})*", raw) and not re.fullmatch(r"\d+", raw.replace(".", "")):
        # allow 16.555.811.753
        digits = raw.replace(".", "")
        if digits.isdigit():
            return int(digits)
        return None
    digits = raw.replace(".", "")
    if digits.isdigit():
        return int(digits)
    return None


def _tr_float_price(token: str) -> Optional[float]:
    """Parse index/fx style: 13.774.77 or 13.774,77 or 47.35 or 4,076 or 6.205,49 or 64.667"""
    t = token.strip().replace(" ", "")
    if not t:
        return None
    # strip trailing dots from truncated "0.57..."
    t = t.rstrip(".")
    # 4,076 -> 4076 (US thousands)
    if re.fullmatch(r"\d{1,3}(,\d{3})+", t):
        return float(t.replace(",", ""))
    # 6.205,49 or 13.773,98 (TR decimal comma)
    if "," in t and "." in t:
        return float(t.replace(".", "").replace(",", "."))
    if "," in t:
        return float(t.replace(",", "."))
    # 13.774.77 (dots as thousands + 2-dec) OR 64.667 (thousand grouping, no decimals)
    if t.count(".") >= 2:
        parts = t.split(".")
        if len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
            # 64.667 / 16.555.811.753 style integer groups
            return float("".join(parts))
        return float("".join(parts[:-1]) + "." + parts[-1])
    if t.count(".") == 1:
        left, right = t.split(".")
        # 64.667 -> 64667 when right side is 3 digits (thousand group)
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
    """Convert raw TL amounts to 亿里拉; strip clock stamps like 18:30."""
    if not text:
        return ""

    def repl_tl(m: re.Match) -> str:
        n = _tr_int(m.group(1))
        if n is None:
            return m.group(0)
        return tl_to_yi_str(n)

    out = re.sub(
        r"(\d{1,3}(?:\.\d{3})+)\s*TL",
        repl_tl,
        text,
        flags=re.I,
    )
    # saat 18:30 itibariyle / 18:30 itibariyle
    out = re.sub(r"saat\s*\d{1,2}:\d{2}\s*itibariyle\s*", "", out, flags=re.I)
    out = re.sub(r"\d{1,2}:\d{2}\s*itibariyle\s*", "", out, flags=re.I)
    out = re.sub(r"（?\s*18:30\s*）?", "", out)
    out = re.sub(r"\b18:30\b", "", out)
    return out


def build_bht_fact_sheet(
    closing_text: str,
    index_override: Optional[dict] = None,
    live_borsa: Optional[dict] = None,
) -> str:
    """Extract factual lines for 大盘/个股/板块/汇市大宗 — Chinese, no analysis.

    index_override (optional): live XU100 snapshot {"last": float, "pct": float}
    from /piyasalar. When supplied, overrides the article's BIST 100 close/pct
    (article has been observed stale/mistyped; live page is authoritative).
    Intraday high/low still come from the article.
    """
    raw = closing_text or ""
    # Strip clocks first so "saat 18:30" does not break gold/oil number capture.
    text = normalize_bht_text(raw)
    lines: list[str] = []
    lines.append(
        "【BHT事实卡｜【大盘概况】【关键个股异动】【行业板块表现】【汇市与大宗商品】"
        "四节只能复述本卡事实，禁止分析、因果、补点位、补涨跌幅、补分时；"
        "里拉成交额必须用「亿里拉」；汇市大宗禁止写任何钟点。】"
    )

    # --- index ---
    high_m = re.search(r"en yüksek\s*([\d.,]+)\s*puan", text, re.I)
    low_m = re.search(r"en düşük\s*([\d.,]+)\s*puan", text, re.I)

    lines.append("【大盘概况事实】")
    bits: list[str] = []
    # Direction-agnostic BIST100 close parser. BHT uses several phrasings:
    #   ... yüzde -1.26 değer kaybederek 13.515.54 puanla ...
    #   ... %-1.26 düşüşle 13.515.54 puandan ...
    #   ... yüzde 1.21 değer kazanarak ... / %1.21 artışla ... / yükselişle ...
    m0 = re.search(
        r"yüzde\s*(-?[\d.,]+)\s*(değer kaybederek|değer kazanarak)\s*([\d.,]+)\s*puan",
        text,
        re.I,
    )
    if not m0:
        m0 = re.search(
            r"%\s*(-?[\d.,]+)\s*(düşüşle|artışla|yükselişle)\s*([\d.,]+)\s*puan",
            text,
            re.I,
        )
    if m0:
        chg_raw = m0.group(1).replace(",", ".").lstrip("+")
        direction_word = m0.group(2).lower()
        close_v = _tr_float_price(m0.group(3))
        if index_override and index_override.get("last") is not None:
            close_v = float(index_override["last"])
            ov_pct = index_override.get("pct")
            if ov_pct is not None:
                chg_raw = f"{float(ov_pct):.2f}"
                is_down = float(ov_pct) < 0
            else:
                is_down = chg_raw.startswith("-") or "kaybe" in direction_word or "düş" in direction_word
        else:
            is_down = chg_raw.startswith("-") or "kaybe" in direction_word or "düş" in direction_word
        chg_disp = chg_raw.lstrip("-")
        verb = "收跌" if is_down else "收涨"
        if close_v is not None:
            bits.append(f"BIST 100 {verb} {chg_disp}%")
            bits.append(f"收盘 {_fmt_pts(close_v)} 点")

    high_v = _tr_float_price(high_m.group(1)) if high_m else None
    low_v = _tr_float_price(low_m.group(1)) if low_m else None
    if high_v is not None:
        bits.append(f"最高 {_fmt_pts(high_v)} 点")
    if low_v is not None:
        bits.append(f"最低 {_fmt_pts(low_v)} 点")
    if high_v is not None and low_v is not None:
        bits.append(f"振幅约 {high_v - low_v:.0f} 点")
    lines.append("；".join(bits) + "。" if bits else "（收盘综述未解析到指数字段）")

    # --- stocks ---
    lines.append("【关键个股异动事实】")
    def _codes(blob: str) -> str:
        codes = [x.strip().upper() for x in blob.split(",") if x.strip()]
        return "、".join(codes)

    live_borsa = live_borsa or {}
    live_volume = live_borsa.get("volume") or []
    if live_volume:
        parts = []
        for item in live_volume[:3]:
            amount = item.get("volume")
            if amount is not None:
                parts.append(f"{item['code']} {tl_to_yi_str(int(amount))}")
        if parts:
            lines.append("实时成交额前三：" + "，".join(parts) + "。")
    else:
        # Match on raw TL amounts (normalize already rewrote them to 亿里拉 in `text`)
        vols = re.findall(
            r"\b([A-Z]{3,6})\s*\((\d{1,3}(?:\.\d{3})+)\s*TL\)",
            raw,
        )
        if vols:
            parts = []
            for code, num in vols[:5]:
                n = _tr_int(num)
                if n is not None:
                    parts.append(f"{code} {tl_to_yi_str(n)}")
            if parts:
                lines.append("成交额前三：" + "，".join(parts[:3]) + "。")

    live_gainers = live_borsa.get("gainers") or []
    live_losers = live_borsa.get("losers") or []
    if live_gainers:
        gain_bits = []
        for item in live_gainers[:5]:
            pct = item.get("pct")
            gain_bits.append(
                f"{item['code']}（{_fmt_pts(float(pct))}%）"
                if pct is not None
                else item["code"]
            )
        lines.append("实时涨幅居前：" + "、".join(gain_bits) + "。")
    if live_losers:
        lose_bits = []
        for item in live_losers[:5]:
            pct = item.get("pct")
            lose_bits.append(
                f"{item['code']}（{_fmt_pts(float(pct))}%）"
                if pct is not None
                else item["code"]
            )
        lines.append("实时跌幅居前：" + "、".join(lose_bits) + "。")

    if not live_gainers and not live_losers:
        gain = re.search(
            r"En çok artan hisseler[\s:]+([A-Za-z0-9_,\s]+?)(?:\s+olurken|\s+olarak|\.|\n)",
            text,
            re.I,
        )
        lose = re.search(
            r"en çok azalan hisseler[\s:]+([A-Za-z0-9_,\s]+?)(?:\s+olarak|\s+olurken|\.|\n)",
            text,
            re.I,
        )
        if gain:
            lines.append(f"涨幅居前：{_codes(gain.group(1))}。")
        if lose:
            lines.append(f"跌幅居前：{_codes(lose.group(1))}。")

    # --- sectors ---
    lines.append("【行业板块表现事实】")
    sec = re.search(
        r"sektörel bazda\s+(.+?)\s+sektörleri yükselirken,\s+(.+?)\s+(?:hisseleri\s+)?en çok düşüş",
        text,
        re.I | re.S,
    )
    if sec:
        up_raw = sec.group(1)
        down_raw = sec.group(2)
        up = _map_sectors(up_raw)
        down = _map_sectors(down_raw)
        lines.append("上涨板块：" + "、".join(up) + "。")
        lines.append("跌幅居前板块：" + "、".join(down) + "。")

    # --- fx / commodities ---
    lines.append("【汇市与大宗商品事实】")
    fx_bits = []
    # Direction-agnostic USD/TRY and EUR/TRY. BHT wording:
    #   ... %0.01 artışla 47.40 TL'de ...   (up)
    #   ... %-0.01 düşüşle 53.97 TL'den ...  (down)
    usd = re.search(
        r"Dolar/TL.*?%(-?[\d.,]+)\s*(artışla|düşüşle|yükselişle)\s*([\d.,]+)\s*TL",
        text,
        re.I | re.S,
    )
    if usd:
        pct = usd.group(1).replace(",", ".").lstrip("+")
        is_down = pct.startswith("-") or "düş" in usd.group(2).lower()
        verb = "下跌" if is_down else "上涨"
        fx_bits.append(
            f"美元/里拉{verb} {pct.lstrip('-')}%，报 {usd.group(3).replace(',', '.')} "
        )
    eur = re.search(
        r"Euro/TL.*?%(-?[\d.,]+)\s*(artışla|düşüşle|yükselişle)\s*([\d.,]+)\s*TL",
        text,
        re.I | re.S,
    )
    if eur:
        pct = eur.group(1).replace(",", ".").lstrip("+")
        is_down = pct.startswith("-") or "düş" in eur.group(2).lower()
        verb = "下跌" if is_down else "上涨"
        fx_bits.append(
            f"欧元/里拉{verb} {pct.lstrip('-')}%，报 {eur.group(3).replace(',', '.')}"
        )
    if fx_bits:
        lines.append("；".join(fx_bits).strip() + "。")

    oz = re.search(
        r"ons altın.*?([\d.,]+)\s*dolar.*?%(-?[\d.,]+)",
        text,
        re.I | re.S,
    )
    # gram altın: BHT writes both "... %X artışla Y lira" and "... %-X düşüşle Y liradan"
    gram = re.search(
        r"gram altın\s+%?(-?[\d.,]+)\s*(artışla|düşüşle|yükselişle)\s*([\d.,]+)\s*lira",
        text,
        re.I,
    )
    gold_bits = []
    if oz:
        pct = oz.group(2).replace(",", ".").lstrip("+").rstrip(".")
        sign = "-" if pct.startswith("-") else ""
        gold_bits.append(
            f"国际金价报 {_fmt_pts(_tr_float_price(oz.group(1)) or 0)} 美元/盎司，"
            f"较前一日变动 {sign}{pct.lstrip('-')}%"
        )
    if gram:
        pct = gram.group(1).replace(",", ".").lstrip("+")
        is_down = pct.startswith("-") or "düş" in gram.group(2).lower()
        sign = "-" if (pct.startswith("-") or is_down) else ""
        gold_bits.append(
            f"克金报 {_fmt_pts(_tr_float_price(gram.group(3)) or 0)} 里拉，"
            f"较前一日{'下跌' if is_down else '上涨'} {pct.lstrip('-')}%"
        )
    cq = re.search(
        r"Çeyrek altının alış fiyatı.*?([\d.,]+)\s*TL.*?satış fiyatı\s*([\d.,]+)\s*TL",
        text,
        re.I | re.S,
    )
    if cq:
        gold_bits.append(
            f"四分之一金币买价 {_fmt_pts(_tr_float_price(cq.group(1)) or 0)} 里拉、"
            f"卖价 {_fmt_pts(_tr_float_price(cq.group(2)) or 0)} 里拉"
        )
    cum = re.search(r"Cumhuriyet altını.*?([\d.,]+)\s*lira", text, re.I)
    if cum:
        gold_bits.append(f"共和国金币报 {_fmt_pts(_tr_float_price(cum.group(1)) or 0)} 里拉")
    if gold_bits:
        lines.append("；".join(gold_bits) + "。")

    brent = re.search(r"Brent petrol.*?([\d.,]+)\s*dolar", text, re.I | re.S)
    if brent:
        lines.append(f"布伦特报 {_fmt_pts(_tr_float_price(brent.group(1)) or 0)} 美元。")

    btc = re.search(r"Bitcoin\s*\$?\s*([\d.]+)", text, re.I)
    eth = re.search(r"Ethereum\s*\$?\s*([\d.,]+)", text, re.I)
    crypto = []
    if btc:
        crypto.append(f"比特币报 {_fmt_pts(_tr_float_price(btc.group(1)) or 0)} 美元")
    if eth:
        crypto.append(f"以太坊报 {_fmt_pts(_tr_float_price(eth.group(1)) or 0)} 美元")
    if crypto:
        lines.append("；".join(crypto) + "。")

    return "\n".join(lines)


def _map_sectors(raw: str) -> list[str]:
    norm = (
        raw.lower()
        .replace("ı", "i")
        .replace("İ", "i")
        .replace("ş", "s")
        .replace("ç", "c")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ö", "o")
    )
    # split on comma / ve / and
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
        # fuzzy contains
        hit = None
        for k, v in SECTOR_CN.items():
            if k in key or key in k:
                hit = v
                break
        out.append(hit or p.strip())
    return out


def format_bloomberght_for_prompt(data: dict, live_quotes: Optional[dict] = None) -> str:
    """Closing text normalized + fact sheet; optional news kept outside factual-card scope.

    live_quotes: full payload from fetch_live_quotes (carries XU100 in quotes
    dict). Used to override the close-review article's BIST 100 numbers. The
    close report runs after market close, so any non-pre_market reading
    (intraday or after_close) reflects TODAY and is preferred over the article.
    """
    raw = (data.get("closing_review") or {}).get("text") or ""
    normalized = normalize_bht_text(raw)
    index_override = None
    live_borsa = {}
    if live_quotes and live_quotes.get("quotes", {}).get("XU100"):
        if live_quotes.get("xu100_status") == "after_close":
            xu = live_quotes["quotes"]["XU100"]
            index_override = {"last": xu.get("last"), "pct": xu.get("pct")}
    if live_quotes and live_quotes.get("xu100_status") == "after_close":
        live_borsa = live_quotes.get("borsa") or {}
    sheet = build_bht_fact_sheet(
        raw,
        index_override=index_override,
        live_borsa=live_borsa,
    )
    blocks = ["【收盘数据｜已换算亿里拉、已去掉钟点】", normalized, "", sheet]
    if live_borsa:
        blocks.extend(["", live_quotes.get("borsa_fact_cn", "")])
    # News intentionally NOT required for the four factual sections
    if data.get("breaking_news"):
        blocks.append("\n【盘中突发｜仅供【核心信号与逻辑】可选引用标题，禁止写进大盘/个股/板块/汇市四节】")
        blocks.extend(data["breaking_news"])
    if data.get("featured_news"):
        blocks.append("\n【重点资讯｜仅供【核心信号与逻辑】可选引用标题，禁止写进大盘/个股/板块/汇市四节】")
        blocks.extend(data["featured_news"])
    return "\n".join(blocks)
