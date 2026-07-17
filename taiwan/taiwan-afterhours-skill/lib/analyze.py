#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘后数据汇总 + 闭环校验器 (数据纪律核心)

读取 data/YYYY-MM-DD/ 下已落盘的原始 JSON, 解析为规范化数字, 运行:
  - 日期门禁 (各源日期戳 == 目标交易日)
  - 收盘闭环: 今收 + 涨跌 = 昨收
  - 法人闭环: 自营(自行)+自营(避险)+投信+外资+外资自营 = 合计
产出 digest.json (经校验数字) + 打印人读摘要, 作为写稿唯一事实源。

用法: python3 lib/analyze.py 2026-07-08
"""
import sys, os, json, re


def num(x):
    if x is None:
        return None
    s = re.sub(r"[,\s]", "", str(x))
    s = re.sub(r"<[^>]+>", "", s)  # 去 <p> 标签
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def load(d, name):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return None
    for enc in ("utf-8", "utf-8-sig", "gbk", "cp950"):
        try:
            with open(p, encoding=enc) as f:
                return json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return None


def foreign_streak(date, lookback=18):
    """外资连续买/卖超天数 —— BFI82U 逐日回溯自算 (官方一手, 免外求)。

    本地优先：先读 data/{wd}/twse_bfi82u.json，缺才补网（与 inst_streak 一致）。
    date: 'YYYY-MM-DD'。返回 {direction, days, cum_e8, series}。网络失败返回 None。"""
    import datetime
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from lib.roots import code_root, data_dir
    from lib.json_io import load_or_none
    try:
        from collectors.twse import fetch_json, build_url
    except Exception:
        return None
    import time
    root = code_root(__file__, up=2)
    base = data_dir(root)
    y, m, dd = map(int, date.split("-"))
    d0 = datetime.date(y, m, dd)
    series = []
    for i in range(lookback):
        dt = d0 - datetime.timedelta(days=i)
        D = dt.strftime("%Y%m%d")
        wd = dt.strftime("%Y-%m-%d")
        # 1) 本地优先
        j = load_or_none(os.path.join(base, wd, "twse_bfi82u.json"))
        fetched = False
        # 2) 缺才补网
        if j is None:
            fetched = True
            j = None
            for _ in range(2):
                try:
                    j = fetch_json(build_url("/fund/BFI82U", {"type": "day", "_datekey": "dayDate"}, D))
                    break
                except Exception:
                    time.sleep(2)
            if j is None:
                # 真·抓取失败: 不可静默跳过(可能漏掉翻转日) -> 截断并标记不可靠
                return {"unreliable": True, "fetched_until": series[-1][0] if series else None,
                        "reason": f"{D} BFI82U 抓取失败, 连续天数不可靠, 需重跑"}
            # 抓到即存（下次复用）
            if j.get("stat") == "OK":
                try:
                    os.makedirs(os.path.join(base, wd), exist_ok=True)
                    from lib.json_io import dump
                    dump(j, os.path.join(base, wd, "twse_bfi82u.json"))
                except Exception:
                    pass
        if j.get("stat") != "OK":
            continue  # 假日/周末: 合法无数据, 跳过
        mm = {r[0]: num(r[3]) for r in j["data"]}
        fore = mm.get("外資及陸資(不含外資自營商)")
        if fore is not None:
            series.append((dt.strftime("%Y-%m-%d"), fore))
    if not series:
        return None
    sign = series[0][1] > 0
    days, cum = 0, 0
    for _, f in series:
        if (f > 0) == sign:
            days += 1
            cum += f
        else:
            break
    return {"direction": "买超" if sign else "卖超", "days": days,
            "cum_e8": round(cum / 1e8, 2),
            "series": [(d, round(f / 1e8, 2)) for d, f in series[:days + 1]]}


def analyze(date):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from lib.roots import code_root, data_dir
    root = code_root(__file__, up=2)
    d = os.path.join(data_dir(root), date)
    dg = {"date": date, "checks": [], "degraded": []}

    # --- 大盘: FMTQIK 量能+收盘 (最后3日) + TAIEX OHLC ---
    fmt = load(d, "twse_fmtqik.json")
    if fmt and fmt.get("data"):
        rows = fmt["data"][-3:]
        dg["taiex"] = [{"date": r[0], "close": num(r[4]), "chg": num(r[5]),
                        "amount_e8": round(num(r[2]) / 1e8, 2)} for r in rows]
    else:
        dg["degraded"].append("大盘量能/收盘(FMTQIK): 未取得")
    ohlc = load(d, "twse_taiex_ohlc.json")
    if ohlc and ohlc.get("data"):
        r = ohlc["data"][-1]
        dg["ohlc"] = {"open": num(r[1]), "high": num(r[2]), "low": num(r[3]), "close": num(r[4])}
        # 前一日收盘
        if len(ohlc["data"]) >= 2:
            dg["prev_close"] = num(ohlc["data"][-2][4])

    # 收盘闭环校验
    if dg.get("taiex"):
        t = dg["taiex"][-1]
        if dg.get("prev_close") is not None:
            calc = round(dg["prev_close"] + t["chg"], 2)
            ok = abs(calc - t["close"]) < 0.05
            dg["checks"].append(["收盘闭环 前收+涨跌=今收",
                                 f"{dg['prev_close']}+{t['chg']}={calc} vs {t['close']}", ok])

    # --- 均线 MA5/10/20 截至当日 (供【大盘】均线与箱体; 盘后有当日真实收盘, 算的是截至今日) ---
    try:
        import os as _os, sys as _sys
        _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
        from lib.ma import compute_ma
        ma = compute_ma(date)
        if ma:
            dg["ma"] = ma
    except Exception as e:
        dg["degraded"].append(f"均线计算失败: {e}")

    # --- 类股指数 (行业) ---
    ind = load(d, "twse_mi_index_ind.json")
    if ind and ind.get("tables") and ind["tables"][0].get("data"):
        sectors = {}
        for r in ind["tables"][0]["data"]:
            name = r[0].strip()
            sectors[name] = {"close": num(r[1]), "chg_pct": num(r[4]), "chg_pt": num(r[3])}
        dg["sectors"] = sectors

    # --- 宽度 (MS) ---
    ms = load(d, "twse_mi_index_ms.json")
    if ms:
        for t in ms["tables"]:
            if "漲跌證券數" in t.get("title", ""):
                dg["breadth"] = {r[0]: {"market": r[1], "stock": r[2]} for r in t["data"]}

    # --- 三大法人分项 (BFI82U) 单位: 元, 转亿 ---
    bfi = load(d, "twse_bfi82u.json")
    if bfi and bfi.get("data"):
        m = {r[0]: num(r[3]) for r in bfi["data"]}
        inst = {
            "自营_自行": m.get("自營商(自行買賣)"),
            "自营_避险": m.get("自營商(避險)"),
            "投信": m.get("投信"),
            "外资": m.get("外資及陸資(不含外資自營商)"),
            "外资自营": m.get("外資自營商"),
            "合计": m.get("合計"),
        }
        dg["inst_net_yuan"] = inst
        dg["inst_net_e8"] = {k: (round(v / 1e8, 2) if v is not None else None) for k, v in inst.items()}
        # 法人闭环
        parts = [inst["自营_自行"], inst["自营_避险"], inst["投信"], inst["外资"], inst["外资自营"]]
        if all(p is not None for p in parts) and inst["合计"] is not None:
            s = sum(parts)
            ok = abs(s - inst["合计"]) < 1
            dg["checks"].append(["法人闭环 分项和=合计", f"{s} vs {inst['合计']}", ok])

    # --- 外资连续买卖天数 (BFI82U 逐日回溯自算) ---
    streak = foreign_streak(date)
    if streak and not streak.get("unreliable"):
        dg["foreign_streak"] = streak
    else:
        reason = streak.get("reason") if streak else "BFI82U 回溯失败"
        dg["degraded"].append(f"外资连续买卖天数: {reason}")

    # --- T86 个股法人买卖超 (股) ---
    t86 = load(d, "twse_t86.json")
    if t86 and t86.get("data"):
        def n(x):
            return num(x) or 0
        rows = [(r[0].strip(), r[1].strip(), n(r[4]), n(r[10]), n(r[18])) for r in t86["data"]]
        dg["t86_foreign_buy"] = [{"code": c, "name": nm, "foreign_lot": round(fb / 1000)}
                                 for c, nm, fb, ti, tt in sorted(rows, key=lambda x: -x[2])[:12]]
        dg["t86_foreign_sell"] = [{"code": c, "name": nm, "foreign_lot": round(fb / 1000)}
                                  for c, nm, fb, ti, tt in sorted(rows, key=lambda x: x[2])[:12]]
        dg["t86_trust_buy"] = [{"code": c, "name": nm, "trust_lot": round(ti / 1000)}
                               for c, nm, fb, ti, tt in sorted(rows, key=lambda x: -x[3])[:8]]
    else:
        dg["degraded"].append("个股法人买卖超(T86): 未取得(常见于16:00前尚未发布)")

    # --- 融资融券: 盘后当日未发布, 按设计归次日早评, 盘后完全不处理、不入降级项 ---
    margn = load(d, "twse_mi_margn.json")
    if margn and margn.get("stat") == "OK":
        # 万一已发布(晚间回补场景)仍存下, 但不作盘后正文/降级用
        t0 = margn["tables"][0]["data"]
        mm = {r[0]: r for r in t0}
        dg["margin"] = {
            "融资金额今日_仟元": num(mm.get("融資金額(仟元)", [None]*6)[5]) if "融資金額(仟元)" in mm else None,
            "融资金额前日_仟元": num(mm.get("融資金額(仟元)", [None]*6)[4]) if "融資金額(仟元)" in mm else None,
        }

    # --- 台指期外资未平仓 (TAIFEX, 由 collector 另存) ---
    tf = load(d, "taifex_net_oi.json")
    if tf:
        dg["taifex"] = tf

    # --- 汇率 (cnyes 〈台幣〉二手同日; 官方源反爬, 此为规范允许的汇率二手) ---
    try:
        from collectors import cnyes
        # 〈台幣〉收盘文午后会被营收速报刷掉, 用分页多翻几页
        arts = cnyes.fetch_recent("tw_stock", pages=6)
        fx_a = cnyes.pick(arts, date, ["台幣"])
        fx = cnyes.parse_fx(fx_a)
        if fx and fx.get("close"):
            fx["source"] = "cnyes〈台幣〉收盘专文"
            dg["fx"] = fx
        else:
            # 〈台幣〉专文常17:20后才出; 深度盘后17:00跑时改从盘后wrap正文取(中午暫收, 二手)
            wrap = cnyes.pick(cnyes.fetch_recent("tw_quo", pages=2) + arts, date, ["〈台股盤後〉", "盤後"])
            fx2 = cnyes.parse_fx(wrap) if wrap else None
            if fx2 and fx2.get("close"):
                fx2["source"] = "盘后wrap正文(中午暫收, 二手同日)"
                dg["fx"] = fx2
            else:
                dg["degraded"].append("汇率: cnyes〈台幣〉与盘后wrap均未得")
    except Exception as e:
        dg["degraded"].append(f"汇率: cnyes 抓取失败({e})")

    return dg


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else None
    dg = analyze(date)
    from lib.roots import code_root, data_dir
    root = code_root(__file__, up=2)
    outp = os.path.join(data_dir(root), date, "digest.json")
    json.dump(dg, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"== digest -> {outp}")
    print("\n[闭环校验]")
    for name, detail, ok in dg["checks"]:
        print(f"  {'✓' if ok else '✗ FAIL'} {name}: {detail}")
    print("\n[大盘]")
    if dg.get("ohlc"):
        o = dg["ohlc"]; print(f"  OHLC 开{o['open']} 高{o['high']} 低{o['low']} 收{o['close']}")
    for t in dg.get("taiex", []):
        print(f"  {t['date']} 收{t['close']} 涨跌{t['chg']} 量{t['amount_e8']}亿")
    print("\n[三大法人(亿)]")
    for k, v in (dg.get("inst_net_e8") or {}).items():
        print(f"  {k}: {v:+.2f}" if v is not None else f"  {k}: NA")
    if dg.get("foreign_streak"):
        s = dg["foreign_streak"]
        print(f"\n[外资连续] {s['direction']} {s['days']} 个交易日, 累计 {s['cum_e8']:+.2f} 亿")
    print("\n[降级项]")
    for x in dg["degraded"]:
        print("  -", x)
