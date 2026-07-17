#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
轻量 T-1 盘后补采 (premarket 内部用, 不跑完整盘后 SOP)。

只采 premarket 必需:
  - twse_stock_all.json (昨收个股表)
  - twse_bfi82u.json    (三大法人分项)
  - taifex_futcontracts.html + taifex_net_oi.json (外资台指期净部位)
  - twse_taiex_ohlc.json (OHLC)
  - digest.json         (收盘闭环; 复用 analyze)
  - 盘前部署handoff_供次日早评.md (复用 handoff)

省去：T86 等待/inst_streak/MI_MARGN/MI_INDEX MS-IND 全表（premarket 不直接用）。
若你日后要完整 T-1, 直接跑 run_afterhours.py。

用法: python3 collect_t1_lite.py YYYYMMDD [prev YYYYMMDD]
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.roots import code_root, data_dir as resolve_data_dir

ROOT = code_root(__file__, up=1)
DATA = resolve_data_dir(ROOT)


def _elapsed(t0):
    return f"{time.time() - t0:.1f}s"


def sh(cmd, label=""):
    print(f"$ {' '.join(cmd)}")
    env = os.environ.copy()
    env["TAIWAN_EQUITY_ROOT"] = ROOT
    env["TAIWAN_EQUITY_DATA"] = DATA
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=ROOT, env=env).returncode
    print(f"[{label}] [elapsed] {_elapsed(t0)} rc={rc}")
    return rc


_LITE_TWSE = """
from collectors.twse import fetch_json
import os
from lib.json_io import dump
base=os.environ['TAIWAN_EQUITY_DATA']
d='{w}'
os.makedirs(os.path.join(base,d), exist_ok=True)
endpoints=[
 ('twse_stock_all','https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date}&type=ALLBUT0999&response=json'),
 ('twse_bfi82u','https://www.twse.com.tw/rwd/zh/fund/BFI82U?type=day&dayDate={date}&response=json'),
 ('twse_taiex_ohlc','https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST?date={date}&response=json'),
]
for key,url in endpoints:
    p=os.path.join(base,d,key+'.json')
    if os.path.exists(p):
        print(f'  [skip] {key} (已存在)'); continue
    try:
        j=fetch_json(url); dump(j, p)
        print(f'  [OK] {key} stat={j.get("stat") if isinstance(j,dict) else "?"}')
    except Exception as e:
        print(f'  [FAIL] {key}: {e}')
"""

_TAIFEX_OI = """
from collectors.taifex import collect, parse_tx_net_oi
import os
from lib.json_io import dump
base=os.environ['TAIWAN_EQUITY_DATA']
collect('{today}', os.path.join(base,'{w}'))
out={{}}
try:
    html=open(os.path.join(base,'{w}','taifex_futcontracts.html'),encoding='utf-8').read()
    net,_=parse_tx_net_oi(html); out={{'foreign_net':net.get('外資')}}
except Exception as e:
    print('  taifex parse fail:',e)
prev={prev!r}
if prev:
    try:
        pw=prev.replace('/','-')
        ph=open(os.path.join(base,pw,'taifex_futcontracts.html'),encoding='utf-8').read()
        pn,_=parse_tx_net_oi(ph); out['prev_foreign_net']=pn.get('外資')
        if out.get('foreign_net') is not None and out.get('prev_foreign_net') is not None:
            out['foreign_net_change']=out['foreign_net']-out['prev_foreign_net']
    except Exception: pass
if out:
    dump(out, os.path.join(base,'{w}','taifex_net_oi.json'))
    print('  taifex_net_oi:',out)
"""


def main():
    today = sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y%m%d")
    prev = sys.argv[2] if len(sys.argv) > 2 else None
    # 8位 -> 民国无关; 接受 '2026/07/16' 或 '20260716' 或 '2026-07-16'
    norm = today.replace("-", "").replace("/", "")
    w = f"{norm[:4]}-{norm[4:6]}-{norm[6:8]}"
    today_arg = f"{norm[:4]}/{norm[4:6]}/{norm[6:8]}"
    t_start = time.time()
    print(f"===== collect_t1_lite  day={today} ({w}) prev={prev} =====")

    sh([sys.executable, "-c", _LITE_TWSE.format(date=norm, w=w)], label="twse_lite")
    sh([sys.executable, "-c", _TAIFEX_OI.format(today=today_arg, w=w, prev=prev)], label="taifex_lite")

    # 复用 analyze/handoff 生成 digest + handoff (analyze 已本地优先, 快)
    if sh([sys.executable, "lib/analyze.py", w], label="analyze") == 0:
        sh([sys.executable, "lib/handoff.py", w], label="handoff")
    else:
        print("  [WARN] analyze 失败, 跳过 handoff (盘前将缺昨日闭环摘要)")

    print(f"[total] {_elapsed(t_start)}")


if __name__ == "__main__":
    main()
