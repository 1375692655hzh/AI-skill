#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钜亨(cnyes) 新闻 JSON API 客户端 —— 保底方案数据源 + 汇率(二手同日)来源。

发现: 列表 API 本身即含全文 content/summary, 无需详情页, 纯 HTTP 无 JS/无挑战。
  列表: https://api.cnyes.com/media/api/v1/newslist/category/{cat}?limit=N
  分类: tw_quo(盤勢, 每日〈台股盤後〉~14:20 /〈台股開盤〉~09:40 wrap)
        tw_stock(台股新闻) / tw_forex(外汇, 〈台幣〉日更)

纪律: 每篇 publishAt 换算台北日期做日期门禁; 只用与目标交易日相符的文。
      cnyes 数字为 T3 二手, 仅用于保底降级版, 须显著标注来源=钜亨。
"""
import json, re, html, urllib.request, time, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.ssl_util import urlopen as ssl_urlopen

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}
API = "https://api.cnyes.com/media/api/v1/newslist/category/{cat}?limit={n}"


def fetch_category(cat, n=30, page=1, retries=4):
    url = API.format(cat=cat, n=n) + f"&page={page}"
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with ssl_urlopen(req, timeout=20) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            return d["items"]["data"]
        except Exception as e:
            last = e; time.sleep(2 * (a + 1))
    raise RuntimeError(f"cnyes {cat} 抓取失败: {last}")


def fetch_recent(cat, pages=5, n=30):
    """跨多页抓取, 覆盖当日全部时段 (盘前要闻~05:10 即便午后被埋也能翻到)。"""
    out = []
    for p in range(1, pages + 1):
        try:
            out += fetch_category(cat, n=n, page=p)
        except Exception:
            break
        time.sleep(0.6)
    return out


def taipei_date(publish_at):
    """unix秒 -> 台北日期 'YYYY-MM-DD' (不依赖本地时区; UTC+8)"""
    t = time.gmtime(publish_at + 8 * 3600)
    return time.strftime("%Y-%m-%d", t)


def clean(text):
    return re.sub(r"<[^>]+>", "", html.unescape(text or "")).strip()


def pick(articles, target_date, title_includes, must_all=False):
    """返回目标日期、标题含关键词的最新一篇 (title_includes: list)"""
    for it in articles:
        if taipei_date(it["publishAt"]) != target_date:
            continue
        t = it.get("title", "")
        hit = (all(k in t for k in title_includes) if must_all
               else any(k in t for k in title_includes))
        if hit:
            return it
    return None


def parse_us_indices(article):
    """从〈台股盤前要聞〉解析隔夜美股四大指数 (点数/涨跌%/收盘)。二手同日。"""
    if not article:
        return None
    c = clean(article.get("content", ""))
    out = {}
    pats = {"道琼": r"道瓊[^\d]*?(下跌|上漲|漲|跌)?\s*([\d,]+\.?\d*)\s*點?或\s*([\d.]+)%[^\d]*?收\s*([\d,]+\.?\d*)",
            "纳斯达克": r"那斯達克[^\d]*?(下跌|上漲|漲|跌)?\s*([\d,]+\.?\d*)\s*點?或\s*([\d.]+)%[^\d]*?收\s*([\d,]+\.?\d*)",
            "标普500": r"S&P\s*500[^\d]*?(下跌|上漲|漲|跌)?\s*([\d,]+\.?\d*)\s*點?或\s*([\d.]+)%[^\d]*?收\s*([\d,]+\.?\d*)",
            "费半": r"費(?:城)?半(?:導體)?[^\d]*?(下跌|上漲|漲|跌)?\s*([\d,]+\.?\d*)\s*點?或\s*([\d.]+)%[^\d]*?收\s*([\d,]+\.?\d*)"}
    import re as _re
    for name, p in pats.items():
        m = _re.search(p, c)
        if m:
            sign = -1 if (m.group(1) in ("下跌", "跌")) else 1
            out[name] = {"chg_pt": sign * float(m.group(2).replace(",", "")),
                         "chg_pct": sign * float(m.group(3)),
                         "close": float(m.group(4).replace(",", ""))}
    return out or None


def parse_fx(fx_article):
    """从〈台幣〉文解析: 收盘价 / 升贬幅度。返回 dict 或 None。"""
    if not fx_article:
        return None
    c = clean(fx_article.get("content", "")) or fx_article.get("summary", "")
    title = fx_article.get("title", "")
    # 收盘价: 多种表述 "收在32.03元" / "32.17元作收" / "收32.03元" / "終場...32.17元"
    close = (re.search(r"收在?\s*([0-9]{2}\.[0-9]+)\s*元", c)
             or re.search(r"([0-9]{2}\.[0-9]+)\s*元\s*作收", c)
             or re.search(r"終場[^。]*?([0-9]{2}\.[0-9]+)\s*元", c)
             or re.search(r"收\s*([0-9]{2}\.[0-9]+)\s*元", title))
    # 升贬: "升值1.11角" / "微升0.8分" / "貶值1.04角" / "翻升...0.8分"
    move = (re.search(r"(升值|貶值|微升|微貶|翻升|翻貶)\s*達?\s*([0-9.]+)\s*(角|分)", c)
            or re.search(r"(升|貶)\s*([0-9.]+)\s*(角|分)", c))
    out = {"raw_title": title, "close": None, "move": None}
    if close:
        out["close"] = float(close.group(1))
    if move:
        mv = move.group(1).replace("翻", "").replace("微", "")
        mv = {"升": "升值", "貶": "貶值"}.get(mv, mv)
        out["move"] = f"{mv}{move.group(2)}{move.group(3)}"
    return out


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y-%m-%d")
    quo = fetch_category("tw_quo", 20)
    stock = fetch_category("tw_stock", 40)
    print(f"== cnyes 盤勢 {date} ==")
    after = pick(quo, date, ["〈台股盤後〉", "台股盤後", "盤後"])
    before = pick(quo, date, ["〈台股開盤〉", "台股開盤", "開盤"])
    fx_a = pick(stock, date, ["台幣"])
    for label, a in [("盘后wrap", after), ("盘前/开盘wrap", before)]:
        print(f"\n[{label}] {a['title'] if a else '(当日无)'}")
        if a:
            print("  ", clean(a.get("content", ""))[:200])
    print(f"\n[汇率] {parse_fx(fx_a)}")
