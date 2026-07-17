#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘后 → 次日盘前 部署交接生成器 (确定性, 从盘后 digest 提炼)。

盘后内参不含「次日展望」, 该内容由本模块产出 handoff 文件, 供次日 run_premarket 读入【盘前策略】。
交接: 部位定调 / 关键位(上压下撑) / 可证伪阈值 / 常设风险 / 待次日盘前刷新的隔夜锚。

用法: python3 lib/handoff.py 2026-07-09   -> data/2026-07-09/盘前部署handoff_供次日早评.md
"""
import sys, os, json, math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.roots import code_root, data_dir as resolve_data_dir
ROOT = code_root(__file__, up=2)
DATA = resolve_data_dir(ROOT)


def _fmt(n, d=0):
    try:
        return f"{n:,.{d}f}"
    except (TypeError, ValueError):
        return "—"


def build_handoff(date, dg):
    ohlc = dg.get("ohlc") or {}
    close, high, low = ohlc.get("close"), ohlc.get("high"), ohlc.get("low")
    inst = dg.get("inst_net_e8") or {}
    fore = inst.get("外资")
    streak = dg.get("foreign_streak") or {}
    tf = dg.get("taifex") or {}
    net = tf.get("foreign_net")
    chg = tf.get("foreign_net_change")

    # 部位定调
    pos = []
    if fore is not None:
        d = "卖超" if fore < 0 else "买超"
        s = f"外资现货{d}{_fmt(abs(fore),2)}亿"
        if streak.get("days"):
            s += f"、已连续{streak['days']}个交易日{streak.get('direction','')}(累计{_fmt(streak.get('cum_e8'),0)}亿)"
        pos.append(s)
    if net is not None:
        side = "净空" if net < 0 else "净多"
        s = f"台指期外资{side}{_fmt(abs(net))}口"
        if chg is not None:
            s += f"(较前日{'增' if (net<0)==(chg<0) and chg!=0 else '减'}{_fmt(abs(chg))}口)"
        pos.append(s)
    if fore is not None:
        stance = "防御分批、不宜追高" if fore < 0 else "偏多可加码、留意追高风险"
        posture = f"外资期现{'同向偏空' if fore < 0 and (net or 0) < 0 else '方向分歧'}，短线姿态{stance}"
    else:
        posture = "法人数据不足，姿态待次日盘前据最新数据定"

    # 关键位: 今高/今低 + 最近整数关
    lv = []
    if high:
        up_int = math.ceil(high / 500) * 500
        lv.append(f"上方压力＝今日高点{_fmt(high,2)}、整数关{_fmt(up_int)}")
    if low:
        dn_int = math.floor(low / 500) * 500
        lv.append(f"下方防线＝今日低点{_fmt(low,2)}、整数关{_fmt(dn_int)}(此位为多空分水岭)")
    keylevels = "；".join(lv) if lv else "关键位待次日盘前据夜盘期指与ADR锚定"

    # 可证伪
    falsify = (f"外资现货卖超收敛至百亿以内、且台指期净空单转为减少→反弹延续；"
               f"若跌破{_fmt(low,2) if low else '今日低点'}→回测下方整数关，反弹证伪"
               if (fore or 0) < 0 else
               f"外资持续买超且期指空单收敛→多方延续；若外资转卖、跌破{_fmt(low,2) if low else '今日低点'}→转弱")

    md = f"""# 盘前部署交接（{date} 盘后 → 并入次日早评）

> 自动生成(确定性, 源自盘后digest)。盘后内参不自带「盘前部署」，改由本文件交接给次日早评的【盘前策略】。
> 次日盘前须用**最新隔夜美股/ADR/夜盘期指**刷新「隔夜锚」，其余以本文件为 T-1 基准再更新。

- **部位定调（T-1 基准）**：{('；'.join(pos)) if pos else '法人/期货数据未取得'}。{posture}。
- **关键位（T-1）**：{keylevels}。
- **可证伪条件**：{falsify}。
- **常设风险**：除权息旺季股息回流与融券强制回补日程；第二季法说密集期个股财报撞期波动。
- **待次日盘前刷新**：隔夜美股(道琼/标普/纳指/费半)、台系ADR(TSM/UMC/ASX)溢价折价、台指期夜盘——由 run_premarket 的 OpenD/cnyes 采集补齐。
"""
    return md


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else None
    dp = os.path.join(DATA, date, "digest.json")
    if not os.path.exists(dp):
        print(f"handoff: 无 digest.json ({dp}), 跳过", file=sys.stderr)
        sys.exit(0)
    dg = json.load(open(dp, encoding="utf-8"))
    # 只有实际交易(有ohlc/收盘)才产出交接, 休市日跳过
    if not (dg.get("ohlc") or dg.get("taiex")):
        print("handoff: 当日无大盘数据(疑休市), 不产出交接", file=sys.stderr)
        sys.exit(0)
    md = build_handoff(date, dg)
    outp = os.path.join(DATA, date, "盘前部署handoff_供次日早评.md")
    open(outp, "w", encoding="utf-8").write(md)
    print(f"✅ handoff -> {outp}")


if __name__ == "__main__":
    main()
