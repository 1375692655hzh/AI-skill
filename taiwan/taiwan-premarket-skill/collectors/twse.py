#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TWSE 官方 rwd 端点采集器 (T1 一手数据, 数字的合法来源之一)

纪律:
- 只用 rwd 端点 (带 date 参数, 无 CDN 缓存); 禁用 openapi.twse.com.tw/v1 (无日期+缓存)
- 每个响应自带日期字段, 必须与目标交易日精确匹配 (日期门禁)
- 瞬时限流是常态 -> 指数退避重试 + 端点间礼貌延迟
- 原始 JSON 落盘 data/YYYY-MM-DD/twse_<key>.json 供对账

用法:
    python3 collectors/twse.py 20260708          # 采集并落盘
    python3 collectors/twse.py 20260708 --summary # 采集+打印校验摘要
"""
import sys, os, json, time, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.ssl_util import urlopen as ssl_urlopen

TAIPEI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://www.twse.com.tw/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,zh;q=0.9",
}
BASE = "https://www.twse.com.tw/rwd/zh"

# 端点定义: key -> (path, 固定query, 说明)
ENDPOINTS = {
    "mi_index_ind": ("/afterTrading/MI_INDEX", {"type": "IND"}, "价格指数全表(含各类股指数)"),
    "mi_index_ms":  ("/afterTrading/MI_INDEX", {"type": "MS"},  "大盘统计+市场宽度"),
    "bfi82u":       ("/fund/BFI82U",           {"type": "day", "_datekey": "dayDate"}, "三大法人买卖金额(分项)"),
    "t86":          ("/fund/T86",              {"selectType": "ALLBUT0999"}, "三大法人个股买卖超明细"),
    "mi_margn":     ("/marginTrading/MI_MARGN",{"selectType": "ALL"}, "融资融券余额"),
    "fmtqik":       ("/afterTrading/FMTQIK",   {}, "每日成交概况(量能)"),
}


def roc_to_west(roc_date):
    """日期串 -> '2026-07-08'。支持:
       民国 '115/07/08' / '115年07月08日'; 西元 8 位 '20260708' / '2026-07-08'。失败返回 None"""
    if not roc_date:
        return None
    s = str(roc_date).strip()
    # 纯 8 位数字 = 西元 YYYYMMDD
    if s.isdigit() and len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    s = s.replace("年", "/").replace("月", "/").replace("日", "").replace("-", "/").strip()
    parts = [p for p in s.split("/") if p]
    if len(parts) != 3:
        return None
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    if y < 1911:  # 民国
        y += 1911
    return f"{y:04d}-{m:02d}-{d:02d}"


def fetch_json(url, retries=6, base_delay=2.0):
    """带指数退避的 JSON 抓取。TWSE 限流时返回空/HTML, 视为失败重试。"""
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=TAIPEI_HEADERS)
            with ssl_urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)   # 空响应/HTML -> JSONDecodeError -> 重试
            return data
        except (json.JSONDecodeError, urllib.error.URLError, ValueError) as e:
            last_err = e
            delay = base_delay * (2 ** attempt)
            time.sleep(min(delay, 20))
    raise RuntimeError(f"抓取失败(已重试{retries}次): {url}\n  末次错误: {last_err}")


def build_url(path, fixed, date):
    q = dict(fixed)
    datekey = q.pop("_datekey", "date")
    q[datekey] = date
    q["response"] = "json"
    qs = "&".join(f"{k}={v}" for k, v in q.items())
    return f"{BASE}{path}?{qs}"


def extract_date(data):
    """从响应中提取西元日期戳; 多路径回退。"""
    import re
    if not isinstance(data, dict):
        return None
    # 1. 顶层 date 字段
    if data.get("date"):
        wd = roc_to_west(str(data["date"]))
        if wd:
            return wd
    # 2. title / tables[].title 中的民国纪年
    titles = [data.get("title", "")] + [t.get("title", "") for t in (data.get("tables") or [])]
    for title in titles:
        if not title:
            continue
        m = re.search(r"(\d{2,3})年(\d{1,2})月(\d{1,2})日", title)
        if m:
            return roc_to_west(f"{m.group(1)}/{m.group(2)}/{m.group(3)}")
    # 3. data 行内首列日期 (如 FMTQIK '115/07/08'); 取最后一行 (当日)
    rows = data.get("data") or []
    if rows and isinstance(rows[-1], list) and rows[-1]:
        wd = roc_to_west(str(rows[-1][0]))
        if wd:
            return wd
    return None


def collect(date, outdir):
    """采集全部端点, 落盘原始 JSON, 返回 {key: {data, west_date, ok}}"""
    os.makedirs(outdir, exist_ok=True)
    target_west = roc_to_west(f"{int(date[:4]) - 1911}/{date[4:6]}/{date[6:8]}")
    results = {}
    for i, (key, (path, fixed, desc)) in enumerate(ENDPOINTS.items()):
        if i > 0:
            time.sleep(2.5)  # 端点间礼貌延迟, 降低限流
        url = build_url(path, fixed, date)
        try:
            data = fetch_json(url)
        except RuntimeError as e:
            print(f"  [FAIL] {key:12s} {desc}: {e}", file=sys.stderr)
            results[key] = {"data": None, "west_date": None, "ok": False, "error": str(e)}
            continue
        raw_path = os.path.join(outdir, f"twse_{key}.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        wd = extract_date(data)
        stat = data.get("stat") if isinstance(data, dict) else None
        # 日期门禁
        date_ok = (wd == target_west)
        results[key] = {"data": data, "west_date": wd, "ok": True,
                        "date_ok": date_ok, "stat": stat, "desc": desc}
        flag = "OK " if date_ok else "!!DATE-MISMATCH!!"
        print(f"  [{flag}] {key:12s} west_date={wd} stat={stat} <- {desc}")
    results["_target_west"] = target_west
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 collectors/twse.py YYYYMMDD [--summary]", file=sys.stderr)
        sys.exit(1)
    date = sys.argv[1]
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from lib.roots import code_root, data_dir
    root = code_root(__file__, up=2)
    west = roc_to_west(f"{int(date[:4]) - 1911}/{date[4:6]}/{date[6:8]}")
    outdir = os.path.join(data_dir(root), west)
    print(f"== TWSE 采集 date={date} (西元 {west}) -> {outdir}")
    res = collect(date, outdir)
    print(f"== 完成. 目标交易日 {res['_target_west']}")
