#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台指期夜盘(盘后交易时段)收盘采集 —— 盘前开盘锚的官方一手来源。

TAIFEX futDailyMarketReport marketCode=1(盤後/夜盘): 台指期(TX)近月 开高低收+涨跌。
夜盘 05:00 收盘, 盘前(08:xx)跑时已就位。日盘 marketCode=0 作对照。

用法: python3 collectors/taifex_night.py 2026/07/14
import: night_tx(date) -> {'close','open','high','low','chg', 'day_close'} 或 None
"""
import sys, os, io, time, urllib.request, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.ssl_util import urlopen as ssl_urlopen

URL = "https://www.taifex.com.tw/cht/3/futDailyMarketReport"
H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
     "Referer": "https://www.taifex.com.tw/cht/3/futDailyMarketReport"}


def _fetch(date, market_code, retries=5):
    data = urllib.parse.urlencode({
        "queryType": "2", "marketCode": market_code,
        "commodity_id": "TX", "queryDate": date}).encode()
    for a in range(retries):
        try:
            req = urllib.request.Request(URL, data=data, headers=H)
            return ssl_urlopen(req, timeout=25).read().decode("utf-8", "replace")
        except Exception:
            time.sleep(2 * (a + 1))
    return None


def _parse_tx(html):
    import pandas as pd
    if not html:
        return None
    try:
        tabs = pd.read_html(io.StringIO(html))
    except ValueError:
        return None
    for t in tabs:
        if "TX" not in str(t.values):
            continue
        for _, row in t.iterrows():
            rv = [str(x) for x in row.values]
            if rv and rv[0].strip() == "TX":
                def num(x):
                    x = x.replace("▼", "-").replace("▲", "+").replace(",", "").strip()
                    try:
                        return float(x)
                    except ValueError:
                        return None
                # 列: 契约,月份,开,高,低,最后成交,涨跌价,涨跌%
                chg = rv[6].replace("▼", "-").replace("▲", "+").replace("--", "-").strip()
                return {"open": num(rv[2]), "high": num(rv[3]), "low": num(rv[4]),
                        "close": num(rv[5]), "chg": chg}
    return None


def night_tx(date):
    """date: 'YYYY/MM/DD'。返回夜盘 TX 收盘 + 日盘对照。"""
    night = _parse_tx(_fetch(date, "1"))
    if not night or night.get("close") is None:
        return None
    time.sleep(1.5)
    day = _parse_tx(_fetch(date, "0"))
    out = dict(night)
    out["day_close"] = day.get("close") if day else None
    return out


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y/%m/%d")
    r = night_tx(date)
    if r:
        print(f"台指期夜盘 {date}: 开{r['open']} 高{r['high']} 低{r['low']} 收{r['close']} 涨跌{r['chg']}")
        if r.get("day_close"):
            diff = r["close"] - r["day_close"]
            print(f"  日盘收{r['day_close']} -> 夜盘{r['close']} ({'+' if diff>=0 else ''}{diff:.0f}, 隐含开盘{'偏多' if diff>0 else '偏空' if diff<0 else '平'})")
    else:
        print("夜盘 TX 未取得")
