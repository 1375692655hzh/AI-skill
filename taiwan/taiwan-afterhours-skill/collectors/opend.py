#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenD(富途) 美股/ADR/费半采集器 —— 盘前 T2 一手数据。

实测(2026-07-08)可得:
  - ADR: US.TSM / US.UMC / US.ASX (台系 ADR, 算溢价折价)
  - 费半成分个股: NVDA/AMD/AVGO/MU/INTC/AMAT/LRCX/ASML
  - 代理: US.SOXX(费半ETF) / US.USO(油) / US.GLD(金)
实测不可得(改由 cnyes 盘前要闻二手补): 美股四大指数点位(DJI/SPX/IXIC/SOX index)、美期指(无行情权限)。

ADR 溢价折价: ADR收盘(USD) × USDTWD ÷ ratio ÷ 台北昨收 − 1
  普通股换算比: TSM 5, UMC 5, ASX 2。

须以 ~/Desktop/futu-trader/.venv 的 python 运行 (默认 python3 无 futu) + OpenD 11111。
用法: ~/Desktop/futu-trader/.venv/bin/python collectors/opend.py [台北昨收json] [usdtwd]
"""
import sys, json

ADR = {  # code -> (名称, 台股代号, 1ADR=N普通股)
    "US.TSM": ("台积电ADR", "2330", 5),
    "US.UMC": ("联电ADR", "2303", 5),
    "US.ASX": ("日月光ADR", "3711", 2),
}
SOX_MEMBERS = ["US.NVDA", "US.AMD", "US.AVGO", "US.MU", "US.INTC",
               "US.AMAT", "US.LRCX", "US.ASML", "US.KLAC", "US.QCOM"]
PROXY = {"US.SOXX": "费半ETF", "US.USO": "油价ETF", "US.GLD": "金价ETF"}
# 美股四大指数 ETF 代理: futu 无指数点位, 用 ETF 涨跌幅(价格是ETF价非点位, 须标注代理)
INDEX_PROXY = {"US.DIA": "道琼", "US.SPY": "标普500", "US.QQQ": "纳指"}


def snapshot(host="127.0.0.1", port=11111):
    from futu import OpenQuoteContext
    q = OpenQuoteContext(host=host, port=port)
    try:
        syms = list(ADR) + SOX_MEMBERS + list(PROXY) + list(INDEX_PROXY)
        ret, data = q.get_market_snapshot(syms)
        out = {"ok": ret == 0, "quotes": {}}
        if ret == 0:
            for _, r in data.iterrows():
                out["quotes"][r["code"]] = {
                    "last": r.get("last_price"),
                    "prev_close": r.get("prev_close_price"),
                    "chg_pct": (round((r.get("last_price") / r.get("prev_close_price") - 1) * 100, 2)
                                if r.get("prev_close_price") else None),
                    "update_time": r.get("update_time"),
                }
        else:
            out["error"] = str(data)
        return out
    finally:
        q.close()


def adr_premium(quotes, taipei_prev_close, usdtwd):
    """taipei_prev_close: {台股代号: 昨收}; usdtwd: float。返回各 ADR 溢价折价%。"""
    out = {}
    for code, (name, tw_code, ratio) in ADR.items():
        q = quotes.get(code)
        prev = taipei_prev_close.get(tw_code) if taipei_prev_close else None
        if not q or q["last"] is None or not prev or not usdtwd:
            out[tw_code] = {"name": name, "premium_pct": None, "note": "缺 ADR价/台北昨收/汇率"}
            continue
        implied = q["last"] * usdtwd / ratio          # ADR 折算台北隐含价
        prem = round((implied / prev - 1) * 100, 2)
        out[tw_code] = {"name": name, "adr_usd": q["last"], "implied_twd": round(implied, 2),
                        "taipei_prev": prev, "premium_pct": prem}
    return out


if __name__ == "__main__":
    # --json <prev_close.json> <usdtwd> <out.json>: 供 run_premarket 子进程调用
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        prev_close = json.load(open(sys.argv[2])) if len(sys.argv) > 2 and sys.argv[2] != "-" else {}
        usdtwd = float(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "-" else None
        outp = sys.argv[4] if len(sys.argv) > 4 else None
        snap = snapshot()
        snap["adr_premium"] = adr_premium(snap.get("quotes", {}), prev_close, usdtwd) if usdtwd else {}
        js = json.dumps(snap, ensure_ascii=False, indent=1)
        if outp:
            open(outp, "w", encoding="utf-8").write(js)
            print(f"opend json -> {outp} ok={snap['ok']}")
        else:
            print(js)
        sys.exit(0)
    prev_close = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else {}
    usdtwd = float(sys.argv[2]) if len(sys.argv) > 2 else None
    snap = snapshot()
    print("== OpenD 快照 ok=", snap["ok"])
    for c, q in snap.get("quotes", {}).items():
        nm = ADR.get(c, (c,))[0] if c in ADR else PROXY.get(c, c)
        print(f"  {c:10s} {str(nm):10s} last={q['last']} chg={q['chg_pct']}% t={q['update_time']}")
    if usdtwd:
        print(f"\n== ADR 溢价折价 (USDTWD={usdtwd}) ==")
        for tw, v in adr_premium(snap["quotes"], prev_close, usdtwd).items():
            print(f"  {tw} {v['name']}: {v.get('premium_pct')}%  (ADR {v.get('adr_usd')}→隐含 {v.get('implied_twd')} vs 昨收 {v.get('taipei_prev')})")
