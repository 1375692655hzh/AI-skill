#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
法人连续买卖超个股 —— T86 逐日回溯自算 (官方一手, 揭示性偏好核心)。

对应元大网页「三大法人连续几日买/卖超」的个股清单, 但改由 TWSE T86 官方数据自算,
可对账、可复现。计算外资(col4)/投信(col10)/三大法人(col18) 各自的连续买/卖天数。

用法: python3 lib/inst_streak.py 2026-07-08 [window=10]
     import: streaks = compute(date, window=10); top = summarize(streaks)
"""
import sys, os, re, time, datetime, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.twse import fetch_json, build_url

IDX = {"foreign": 1, "trust": 2, "all3": 3}  # tuple 位: (name, 外资, 投信, 三大法人)


def _n(x):
    s = re.sub(r"[,]", "", str(x))
    try:
        return int(s)
    except ValueError:
        return 0


def fetch_t86_history(date, window=10, cache_dir=None):
    """回溯 window 个交易日的 T86, 返回 {date: {code:(name,foreign,trust,all3)}}。"""
    y, m, d = map(int, date.split("-"))
    d0 = datetime.date(y, m, d)
    hist = {}
    got, i = 0, 0
    while got < window and i < window + 12:
        dt = d0 - datetime.timedelta(days=i)
        i += 1
        D = dt.strftime("%Y%m%d")
        wd = dt.strftime("%Y-%m-%d")
        # 本地缓存优先
        cache = os.path.join(cache_dir, wd, "twse_t86.json") if cache_dir else None
        j = None
        if cache and os.path.exists(cache):
            try:
                j = json.load(open(cache, encoding="utf-8"))
            except Exception:
                j = None
        if j is None:
            try:
                j = fetch_json(build_url("/fund/T86", {"selectType": "ALLBUT0999"}, D))
            except Exception:
                time.sleep(1.5); continue
            time.sleep(2.3)
            # 抓取即缓存, 下次复用免重抓
            if cache_dir and j.get("stat") == "OK":
                try:
                    os.makedirs(os.path.join(cache_dir, wd), exist_ok=True)
                    json.dump(j, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
                except Exception:
                    pass
        if j.get("stat") != "OK":
            continue
        m2 = {}
        for r in j["data"]:
            if len(r) < 19:
                continue
            m2[r[0].strip()] = (r[1].strip(), _n(r[4]), _n(r[10]), _n(r[18]))
        hist[wd] = m2
        got += 1
    return hist


def compute(date, window=10, cache_dir=None):
    hist = fetch_t86_history(date, window, cache_dir)
    dates = sorted(hist.keys(), reverse=True)
    if not dates:
        return None
    codes = set(hist[dates[0]].keys())
    capped = len(dates)

    def streak(code, pos):
        seq = []
        for d in dates:
            if code in hist[d]:
                seq.append(hist[d][code][pos])
            else:
                break
        if not seq or seq[0] == 0:
            return None
        sign = seq[0] > 0
        cnt, cum = 0, 0
        for v in seq:
            if v != 0 and (v > 0) == sign:
                cnt += 1; cum += v
            else:
                break
        return {"dir": "买超" if sign else "卖超", "days": cnt, "today": seq[0],
                "cum": cum, "name": hist[dates[0]][code][0], "capped": cnt >= capped}

    out = {"date": date, "window": capped, "dates": dates, "codes": {}}
    for c in codes:
        out["codes"][c] = {k: streak(c, IDX[k]) for k in IDX}
    return out


def top_list(res, who, direction, min_days=4, n=10):
    """按今日买卖超量级排序的连续榜。who: foreign/trust/all3。"""
    rows = []
    for c, s in res["codes"].items():
        st = s.get(who)
        if st and st["dir"] == direction and st["days"] >= min_days:
            rows.append((c, st["name"], st["days"], st["today"], st["cum"], st["capped"]))
    rows.sort(key=lambda x: (-x[2], -abs(x[3])))
    return rows[:n]


def crossfire(res, min_days=4):
    """土洋对做: 外资与投信方向相反且均连续≥min_days。按外资今日量级排序。"""
    rows = []
    for c, s in res["codes"].items():
        f, t = s.get("foreign"), s.get("trust")
        if f and t and f["days"] >= min_days and t["days"] >= min_days and f["dir"] != t["dir"]:
            rows.append((c, f["name"], f["dir"], f["days"], t["dir"], t["days"], abs(f["today"])))
    rows.sort(key=lambda x: -x[6])
    return rows


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y-%m-%d")
    window = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    from lib.roots import code_root, data_dir
    root = code_root(__file__, up=2)
    res = compute(date, window, cache_dir=data_dir(root))
    if not res:
        print("无数据"); sys.exit(1)
    print(f"== 法人连续买卖超 {date} (窗口{res['window']}交易日, 张) ==")
    lot = lambda v: f"{v/1000:+,.0f}"
    for who, wl in [("foreign", "外资"), ("trust", "投信")]:
        for direction in ["买超", "卖超"]:
            print(f"\n[{wl}连续{direction}]")
            for c, nm, dd, td, cum, cap in top_list(res, who, direction, 4, 8):
                print(f"  {c} {nm:8s} 连{dd}{'+' if cap else ''}日 今{lot(td)} 累{lot(cum)}")
    print("\n[土洋对做 (方向相反, 各≥4日)]")
    for c, nm, fd, fdd, td, tdd, _ in crossfire(res)[:12]:
        print(f"  {c} {nm:8s} 外资{fd}连{fdd}日 / 投信{td}连{tdd}日")
