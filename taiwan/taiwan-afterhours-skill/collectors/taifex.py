#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TAIFEX 期货三大法人未平仓采集器 (T1 一手, 台股定价权最早的方向暴露工具)

取: 臺股期貨(TX) 外資/投信/自營 未平倉多空淨額(口數) -> 外资台指期净空单
    需两日以算日增减。
纪律: 日期门禁(queryDate 回显), 落盘原始 HTML。

用法: python3 collectors/taifex.py 2026/07/08 [2026/07/07]
"""
import sys, os, io, urllib.request, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.ssl_util import urlopen as ssl_urlopen

URL = "https://www.taifex.com.tw/cht/3/futContractsDate"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
           "Referer": "https://www.taifex.com.tw/cht/3/futContractsDate"}

# 臺股期貨表: 前3行 = 自營商/投信/外資 (身份顺序固定)
TX_IDENTITY = {0: "自營商", 1: "投信", 2: "外資"}
# 15列: ...,13=未平倉多空淨額口數,14=未平倉多空淨額金額
COL_NET_OI = 13


def fetch_html(query_date, retries=4):
    import time, json
    data = urllib.parse.urlencode({
        "queryType": "1", "goDay": "", "doQuery": "1",
        "dateaddcnt": "", "queryDate": query_date, "commodityId": ""
    }).encode()
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(URL, data=data, headers=HEADERS)
            with ssl_urlopen(req, timeout=25) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            last = e; time.sleep(2 * (a + 1))
    raise RuntimeError(f"TAIFEX 抓取失败 {query_date}: {last}")


def parse_tx_net_oi(html):
    """返回 {'自營商':口, '投信':口, '外資':口} 臺股期貨未平仓多空净额口数。"""
    import pandas as pd
    tabs = pd.read_html(io.StringIO(html))
    # 取最大表
    t = max(tabs, key=lambda x: x.shape[0] * x.shape[1])
    out = {}
    for ridx, ident in TX_IDENTITY.items():
        try:
            val = t.iloc[ridx, COL_NET_OI]
            out[ident] = int(str(val).replace(",", ""))
        except Exception:
            out[ident] = None
    return out, t.shape


def collect(query_date, outdir):
    os.makedirs(outdir, exist_ok=True)
    html = fetch_html(query_date)
    raw_path = os.path.join(outdir, "taifex_futcontracts.html")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(html)
    # 日期回显门禁: 页面应含 queryDate
    date_echo = query_date in html
    net, shape = parse_tx_net_oi(html)
    return {"query_date": query_date, "date_echo_ok": date_echo,
            "tx_net_oi": net, "table_shape": shape}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 collectors/taifex.py YYYY/MM/DD [prev YYYY/MM/DD]", file=sys.stderr)
        sys.exit(1)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from lib.roots import code_root, data_dir
    root = code_root(__file__, up=2)
    base = data_dir(root)
    today = sys.argv[1]
    west = today.replace("/", "-")
    outdir = os.path.join(base, west)
    r = collect(today, outdir)
    print(f"== TAIFEX {today} date_echo={r['date_echo_ok']} shape={r['table_shape']}")
    print(f"   臺股期貨未平倉多空淨額(口): {r['tx_net_oi']}")
    fx = r["tx_net_oi"].get("外資")
    print(f"   >> 外資台指期淨部位: {fx:+,} 口 ({'淨空' if fx and fx<0 else '淨多'})" if fx is not None else "   >> 外資解析失败")
    if len(sys.argv) >= 3:
        prev = sys.argv[2]
        import time; time.sleep(2)
        rp = collect(prev, os.path.join(base, prev.replace("/", "-")))
        pfx = rp["tx_net_oi"].get("外資")
        print(f"== 前日 {prev} 外資: {pfx:+,} 口" if pfx is not None else "前日解析失败")
        if fx is not None and pfx is not None:
            print(f"   >> 外資淨空日增减: {fx - pfx:+,} 口 ({'空单增加' if fx<pfx else '空单减少'})")
