#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘前 SOP 编排器 (每交易日 08:40 触发) —— 深度盘前合刊数据层。

流程 (规范 §6.1):
  Step1 数字层: OpenD(费半成分/ADR/油金 + ADR溢价) + 本地库存(前一交易日盘后TWSE)
  Step2 叙事层: cnyes〈台股盤前要聞〉(~05:10, 隔夜美股/夜盘/台币/产业焦点/个股营收)
  Step3 交接: 读前一日盘后产出的 盘前部署handoff (部位/关键位/可证伪, 隔夜锚在此刷新)
  Step4 计算: ADR溢价折价、隔夜美股(cnyes二手)、并校验库存日期
  Step5 汇总 -> data/DATE/premarket_digest.json + 摘要, 供 Claude 依 §5 模块规范成稿

数据纪律: 库存(TWSE)与ADR/费半(OpenD)为一手; 美股指数点位/夜盘/台币走cnyes二手同日(须台账标注)。
  Step2 允许失败 -> 静默降级出纯数字层版。

用法: python3 run_premarket.py [target_YYYY-MM-DD] [prev_YYYY-MM-DD]
"""
import sys, os, json, subprocess, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.roots import code_root, data_dir as resolve_data_dir

ROOT = code_root(__file__, up=1)
DATA = resolve_data_dir(ROOT)
FUTU_PY = os.environ.get("TAIWAN_FUTU_PYTHON") or os.path.expanduser(
    os.environ.get("FUTU_PYTHON", "~/Desktop/futu-trader/.venv/bin/python")
)
sys.path.insert(0, ROOT)
from collectors import cnyes
from lib import lexicon  # noqa


def _num2(x):
    import re as _re
    try:
        return float(_re.sub(r"[,]|<[^>]+>", "", str(x)))
    except (ValueError, TypeError):
        return None


def latest_prev_data_dir(target):
    """扫 data/ 找 target 之前最近的、**实际交易过**的日目录。
    休市日(如台风)也会跑出空 digest, 必须以 stock_all 非空(>1000字节)判定真交易, 否则会错把休市日当昨日。"""
    base = DATA
    if not os.path.isdir(base):
        return None
    cands = []
    for d in os.listdir(base):
        if len(d) == 10 and d < target:
            sa = os.path.join(base, d, "twse_stock_all.json")
            if os.path.exists(sa) and os.path.getsize(sa) > 1000:
                cands.append(d)
    return sorted(cands, reverse=True)[0] if cands else None


def load_prev_close(prev_dir, codes=("2330", "2303", "3711")):
    """从库存 stock_all 取指定台股代号昨收。"""
    import re
    p = os.path.join(prev_dir, "twse_stock_all.json")
    if not os.path.exists(p):
        return {}
    d = json.load(open(p, encoding="utf-8"))
    def num(x):
        s = re.sub(r"[,]|<[^>]+>", "", str(x))
        try:
            return float(s)
        except ValueError:
            return None
    for t in d.get("tables", []):
        fs = [str(x) for x in (t.get("fields") or [])]
        if any("證券代號" in x for x in fs) and any("收盤價" in x for x in fs):
            m = {r[0].strip(): num(r[8]) for r in t["data"] if len(r) >= 9}
            return {c: m[c] for c in codes if c in m}
    return {}


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y-%m-%d")
    prev = sys.argv[2] if len(sys.argv) > 2 else latest_prev_data_dir(target)
    outdir = os.path.join(DATA, target)
    os.makedirs(outdir, exist_ok=True)
    dg = {"target": target, "prev_trading_day": prev, "degraded": [], "sources": {}}
    print(f"== 盘前 SOP target={target} prev(库存)={prev}")

    prev_dir = os.path.join(DATA, prev) if prev else None

    # --- Step2 先取 cnyes 盘前要闻 (叙事 + 美股指数 + 台币, 允许失败) ---
    fx_close = None
    try:
        arts = cnyes.fetch_recent("tw_stock", pages=6) + cnyes.fetch_recent("tw_quo", pages=2)
        pre = cnyes.pick(arts, target, ["盤前要聞"]) or cnyes.pick(arts, target, ["〈台股開盤〉", "開盤"])
        if pre:
            dg["cnyes_premarket"] = {"title": pre["title"], "publishAt": pre["publishAt"],
                                     "content": cnyes.clean(pre.get("content", ""))}
            us = cnyes.parse_us_indices(pre)
            if us:
                dg["us_indices_cnyes"] = us
            dg["sources"]["cnyes_盘前要闻"] = pre["title"]
        else:
            dg["degraded"].append("cnyes〈台股盤前要聞〉当日未得")
        fx_a = cnyes.pick(arts, target, ["台幣"])
        fx = cnyes.parse_fx(fx_a)
        if fx and fx.get("close"):
            dg["fx"] = fx
            fx_close = fx["close"]
    except Exception as e:
        dg["degraded"].append(f"cnyes 叙事层失败: {e}")

    # --- Step1 库存(昨收) + OpenD(ADR/费半/溢价) ---
    prev_close = load_prev_close(prev_dir) if prev_dir else {}
    dg["taipei_prev_close"] = prev_close
    prev_fx = None
    if prev_dir and os.path.exists(os.path.join(prev_dir, "digest.json")):
        pd = json.load(open(os.path.join(prev_dir, "digest.json"), encoding="utf-8"))
        dg["prev_afterhours"] = {k: pd.get(k) for k in
                                 ("taiex", "inst_net_e8", "foreign_streak", "taifex", "breadth", "fx")}
        prev_fx = (pd.get("fx") or {}).get("close")

    # --- 均线 (MA5/10/20) 截至昨日, 供【量化体系】20日线分析 ---
    if prev:
        try:
            from lib.ma import compute_ma
            ma = compute_ma(prev)
            if ma:
                dg["ma"] = ma
        except Exception as e:
            dg["degraded"].append(f"均线计算失败: {e}")

    # --- 台指期夜盘 (盘后交易时段 05:00 收盘, 开盘锚官方一手) ---
    try:
        from collectors.taifex_night import night_tx
        nt = night_tx(target.replace("-", "/"))
        if nt and nt.get("close") is not None:
            dg["night_futures"] = nt
        else:
            dg["degraded"].append("台指期夜盘: 未取得")
    except Exception as e:
        dg["degraded"].append(f"台指期夜盘抓取失败: {e}")

    # --- 股市行事历: 未来除权息日程 (官方一手, 供【后续关注】事件日程) ---
    try:
        from collectors.market_calendar import summary as cal_summary
        cal = cal_summary(target)
        if cal.get("exright_upcoming"):
            dg["calendar"] = cal
    except Exception as e:
        dg["degraded"].append(f"行事历采集失败: {e}")

    # --- 融资融券 T-1 (发布太晚赶不上盘后收评, 归早评; 取最近可得, 优先昨日) ---
    try:
        from collectors.twse import fetch_json, build_url
        for md in ([prev.replace("-", "")] if prev else []):
            j = fetch_json(build_url("/marginTrading/MI_MARGN", {"selectType": "ALL"}, md))
            if j.get("stat") == "OK" and j.get("tables"):
                t0 = {r[0]: r for r in j["tables"][0].get("data", [])}
                fin = t0.get("融資金額(仟元)")
                sec = t0.get("融券(交易單位)")
                dg["margin_t1"] = {
                    "date": prev,
                    "融资金额今日_仟元": _num2(fin[5]) if fin else None,
                    "融资金额前日_仟元": _num2(fin[4]) if fin else None,
                    "融券今日_单位": _num2(sec[5]) if sec else None,
                    "融券前日_单位": _num2(sec[4]) if sec else None,
                }
                break
        else:
            dg["degraded"].append("融资融券T-1: 昨日 MI_MARGN 未得")
    except Exception as e:
        dg["degraded"].append(f"融资融券T-1 抓取失败: {e}")

    # ADR 溢价用汇率: 盘前时点今日〈台幣〉收盘未出, 回退用昨日台币收盘(库存)
    usdtwd = fx_close or prev_fx
    if usdtwd and not fx_close:
        dg["adr_fx_note"] = f"ADR溢价用昨日台币收盘 {usdtwd} (今日盘前未出)"
    pc_file = os.path.join(outdir, "_prev_close.json")
    json.dump(prev_close, open(pc_file, "w", encoding="utf-8"), ensure_ascii=False)
    opend_out = os.path.join(outdir, "opend.json")
    if os.path.exists(FUTU_PY):
        try:
            r = subprocess.run([FUTU_PY, os.path.join(ROOT, "collectors/opend.py"), "--json",
                                pc_file, str(usdtwd) if usdtwd else "-", opend_out],
                               capture_output=True, text=True, timeout=60)
            if os.path.exists(opend_out):
                dg["opend"] = json.load(open(opend_out, encoding="utf-8"))
                dg["sources"]["OpenD"] = "ADR/费半成分/油金/美股四大ETF代理 (T2一手)"
                if not dg["opend"].get("ok"):
                    dg["degraded"].append(f"OpenD 快照失败: {dg['opend'].get('error','')[:60]}")
                # 美股四大指数 ETF 代理涨跌幅 (价格是ETF价非点位, 只用涨跌幅, 标注代理)
                q = dg["opend"].get("quotes", {})
                idx = {}
                for sym, name in {"US.DIA": "道琼", "US.SPY": "标普500", "US.QQQ": "纳指"}.items():
                    if q.get(sym) and q[sym].get("chg_pct") is not None:
                        idx[name] = {"chg_pct": q[sym]["chg_pct"], "proxy": sym.split(".")[1]}
                if idx:
                    dg["us_indices_proxy"] = idx
            else:
                dg["degraded"].append(f"OpenD 无输出: {r.stderr[-120:]}")
        except Exception as e:
            dg["degraded"].append(f"OpenD 调用失败: {e}")
    else:
        dg["degraded"].append("OpenD futu venv 不存在")

    # --- Step3 交接 handoff ---
    if prev_dir:
        hp = os.path.join(prev_dir, "盘前部署handoff_供次日早评.md")
        if os.path.exists(hp):
            dg["handoff"] = open(hp, encoding="utf-8").read()
            dg["sources"]["盘前部署handoff"] = os.path.relpath(hp, ROOT)
        else:
            dg["degraded"].append("前一日盘前部署handoff 缺失")

    outp = os.path.join(outdir, "premarket_digest.json")
    json.dump(dg, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 摘要
    print(f"\n[库存昨收] {dg['taipei_prev_close']}")
    if dg.get("us_indices_cnyes"):
        print("[隔夜美股(cnyes二手)]")
        for k, v in dg["us_indices_cnyes"].items():
            print(f"  {k}: {v['close']} ({v['chg_pct']:+}%)")
    if dg.get("opend", {}).get("adr_premium"):
        print("[ADR溢价折价]")
        for tw, v in dg["opend"]["adr_premium"].items():
            print(f"  {tw} {v['name']}: {v.get('premium_pct')}%")
    if dg.get("fx"):
        print(f"[台币] 收{dg['fx']['close']} {dg['fx'].get('move')}")
    print(f"[handoff] {'已载入' if dg.get('handoff') else '缺'}")
    print(f"\n[降级项] {dg['degraded'] or '无'}")
    print(f"== digest -> {outp}  (供 Claude 依 §5 盘前模块成稿)")


if __name__ == "__main__":
    main()
