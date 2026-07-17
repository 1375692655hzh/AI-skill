#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
加权指数均线 (MA5/10/20/月线) 计算 —— 供【量化体系】20日线分析。

FMTQIK 单次返回目标日所在月, 为算 MA20 需跨月拼接。取足够交易日收盘, 计算截至目标日的
MA5/MA10/MA20, 以及当日收盘相对 20 日线的位置与近期穿越状态(跌破/附近/突破)。

用法: python3 lib/ma.py 20260709
import: compute_ma('2026-07-09') -> dict
"""
import sys, os, re, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.twse import fetch_json


def _num(x):
    try:
        return float(re.sub(r"[,]", "", str(x)))
    except (ValueError, TypeError):
        return None


def fetch_closes(date_yyyymmdd, months_back=2):
    """抓目标月及往前 months_back 个月的 FMTQIK 收盘, 返回 [(民国日期, close)] 升序去重。"""
    y, m, d = int(date_yyyymmdd[:4]), int(date_yyyymmdd[4:6]), int(date_yyyymmdd[6:8])
    seen, out = set(), []
    for back in range(months_back + 1):
        mm = m - back
        yy = y
        while mm <= 0:
            mm += 12; yy -= 1
        q = f"{yy}{mm:02d}01"
        try:
            j = fetch_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={q}&response=json")
        except Exception:
            continue
        for r in (j.get("data") or []):
            key = r[0]
            if key in seen:
                continue
            seen.add(key)
            c = _num(r[4])
            if c is not None:
                out.append((key, c))
    # 民国日期排序
    def rockey(roc):
        p = roc.split("/")
        return (int(p[0]), int(p[1]), int(p[2])) if len(p) == 3 else (0, 0, 0)
    out.sort(key=lambda x: rockey(x[0]))
    # 只保留 <= 目标日
    target_roc = f"{y-1911}/{m:02d}/{d:02d}"
    tk = rockey(target_roc)
    return [(dt, c) for dt, c in out if rockey(dt) <= tk]


def compute_ma(date):
    """date: 'YYYY-MM-DD'。返回截至该交易日的 MA 与相对20日线判断; 数据不足返回 None。"""
    ymd = date.replace("-", "")
    closes = fetch_closes(ymd, months_back=2)
    if not closes or closes[-1][0] != f"{int(ymd[:4])-1911}/{ymd[4:6]}/{ymd[6:8]}":
        # 目标日不在序列(休市/未收盘)
        if not closes:
            return None
    vals = [c for _, c in closes]
    n = len(vals)
    close = vals[-1]

    def ma(k):
        return round(sum(vals[-k:]) / k, 2) if n >= k else None

    ma5, ma10, ma20 = ma(5), ma(10), ma(20)
    out = {"date": date, "close": close, "ma5": ma5, "ma10": ma10, "ma20": ma20,
           "n_days": n}
    if ma20:
        out["vs_ma20_pct"] = round((close / ma20 - 1) * 100, 2)
        out["above_ma20"] = close > ma20
        # 近5日相对20日线穿越状态
        recent = vals[-6:]
        # 计算最近若干日每日的 close vs 当日MA20(滚动)
        crossed_below_days = None
        for i in range(1, min(6, n)):  # 往回看最多5日
            idx = n - 1 - i
            if idx >= 19:
                m20_i = round(sum(vals[idx-19:idx+1]) / 20, 2)
                if vals[idx] < m20_i and close is not None:
                    crossed_below_days = i
                    break
        # 型态定性
        band = abs(out["vs_ma20_pct"])
        if band <= 0.5:
            out["ma20_state"] = "贴近20日线, 属均线附近震荡, 方向未定"
        elif close > ma20:
            out["ma20_state"] = f"站上20日线(距+{out['vs_ma20_pct']}%), 中期偏多, 留意能否守稳"
        else:
            out["ma20_state"] = (f"跌破20日线(距{out['vs_ma20_pct']}%), 中期转弱; "
                                 f"须追踪能否3个交易日内迅速收复, 否则趋势下弯")
    return out


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else None
    d = date if "-" in date else f"{date[:4]}-{date[4:6]}-{date[6:8]}"
    r = compute_ma(d)
    print(r)
