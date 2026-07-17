#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股市行事历采集器 —— 供【后续关注】事件日程 (官方一手, 替代 money.udn JS 门户)。

TWSE 官方:
  - 除權除息預告表 TWT48U: 未来除权息日程 (含代号/名称/息或权/无偿配股率)
  - 除權息計算結果 TWT49U: 近日除权息参考价与权值+息值
法说会日程: TWSE rwd 端点不通, 由 cnyes 盘前要闻叙事补 (二手), 本模块只管官方除权息。

用法: python3 collectors/calendar.py 2026-07-14   -> 打印未来7~14日除权息日程
import: upcoming_exright(date, days=10) -> list
"""
import sys, os, re, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.twse import fetch_json, roc_to_west


def _roc_to_date(roc):
    """民国 '115年07月21日' -> date"""
    m = re.search(r"(\d{2,3})年(\d{1,2})月(\d{1,2})日", str(roc))
    if not m:
        w = roc_to_west(roc)
        if w:
            y, mo, d = map(int, w.split("-"))
            return datetime.date(y, mo, d)
        return None
    y, mo, d = int(m.group(1)) + 1911, int(m.group(2)), int(m.group(3))
    return datetime.date(y, mo, d)


def upcoming_exright(target_date, days_ahead=14, max_items=40):
    """返回 target_date 起未来 days_ahead 天的除权息日程 (按日期升序)。"""
    y, mo, d = map(int, target_date.split("-"))
    t0 = datetime.date(y, mo, d)
    t1 = t0 + datetime.timedelta(days=days_ahead)
    out = []
    try:
        j = fetch_json("https://www.twse.com.tw/rwd/zh/exRight/TWT48U?response=json")
    except Exception:
        return out
    for r in (j.get("data") or []):
        dt = _roc_to_date(r[0])
        if dt and t0 <= dt <= t1:
            out.append({
                "date": dt.isoformat(),
                "code": r[1].strip(),
                "name": r[2].strip(),
                "type": r[3].strip(),  # 息/權/權息
            })
    out.sort(key=lambda x: (x["date"], x["code"]))
    return out[:max_items]


def exright_results(target_date, days_back=2):
    """近日(target_date 及前 days_back 日)除权息参考价结果, 供个股填息锚。"""
    y, mo, d = map(int, target_date.split("-"))
    t0 = datetime.date(y, mo, d)
    lo = t0 - datetime.timedelta(days=days_back)
    out = []
    try:
        j = fetch_json("https://www.twse.com.tw/rwd/zh/exRight/TWT49U?response=json")
    except Exception:
        return out
    for r in (j.get("data") or []):
        dt = _roc_to_date(r[0])
        if dt and lo <= dt <= t0:
            out.append({"date": dt.isoformat(), "code": r[1].strip(), "name": r[2].strip(),
                        "prev_close": r[3], "ref_price": r[4], "value": r[5]})
    return out


def summary(target_date):
    """行事历摘要 dict, 供 digest。"""
    up = upcoming_exright(target_date, 14)
    # 按日期聚合
    by_day = {}
    for it in up:
        by_day.setdefault(it["date"], []).append(f"{it['code']}{it['name']}({it['type']})")
    return {"exright_upcoming": up, "exright_by_day": by_day,
            "exright_results": exright_results(target_date, 3)}


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    s = summary(date)
    print(f"== 未来14日除权息日程 (共{len(s['exright_upcoming'])}档) ==")
    for day, items in sorted(s["exright_by_day"].items()):
        print(f"  {day}: {len(items)}档 {', '.join(items[:8])}{'...' if len(items)>8 else ''}")
    print(f"== 近日除权息参考价 (共{len(s['exright_results'])}) ==")
    for r in s["exright_results"][:6]:
        print(f"  {r['date']} {r['code']}{r['name']} 参考价{r['ref_price']} 权值+息值{r['value']}")
