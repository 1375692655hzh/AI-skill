#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘后 SOP 编排器 (每交易日 16:00 触发)

流程 (规范 §6.2):
  Step1 TWSE 官方端点全量拉取 (MI_INDEX IND/MS/ALLBUT0999, BFI82U, T86, MI_MARGN, FMTQIK, TAIEX-OHLC)
  Step2 TAIFEX 期货三大法人未平仓 (今日+前一交易日, 算日增减)
  Step3 汇总 + 闭环校验 (收盘闭环 / 法人闭环 / 日期门禁) -> digest.json
  Step4 打印数据摘要供写稿; 降级项显式标注
成稿(Step5)由 generate_afterhours_report.py 调 compose_report 完成, 不在本脚本内。

用法:
  python3 run_afterhours.py 20260708 [--prev 20260707] [--t86-max-wait-min 35]
环境变量:
  TAIWAN_EQUITY_DATA  共享/独立数据目录
  TAIWAN_T86_MAX_WAIT_MIN  T86 等待分钟(历史日=0 跳过)
"""
import sys, os, subprocess, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.roots import code_root, data_dir as resolve_data_dir

ROOT = code_root(__file__, up=1)
DATA = resolve_data_dir(ROOT)
os.makedirs(DATA, exist_ok=True)


def west(d):
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def _elapsed(t0):
    return f"{time.time() - t0:.1f}s"


def _t86_max_wait_min():
    if "TAIWAN_T86_MAX_WAIT_MIN" in os.environ:
        try:
            return max(0, int(os.environ["TAIWAN_T86_MAX_WAIT_MIN"]))
        except ValueError:
            pass
    return 35


def sh(cmd, *, must_succeed=False, label=""):
    """Run subcommand, return rc. If must_succeed, exit non-zero rc."""
    print(f"\n$ {' '.join(cmd)}")
    env = os.environ.copy()
    env["TAIWAN_EQUITY_ROOT"] = ROOT
    env["TAIWAN_EQUITY_DATA"] = DATA
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=ROOT, env=env).returncode
    tag = f"[{label}] " if label else ""
    print(f"{tag}[elapsed] {_elapsed(t0)} rc={rc}")
    if must_succeed and rc != 0:
        print(f"[ABORT] {label or cmd[0]} 失败 rc={rc}", file=sys.stderr)
        sys.exit(rc)
    return rc


def main():
    # 无参数 -> 默认当天(台北=本机CST同为UTC+8) YYYYMMDD, 供 launchd 定时调用
    date = sys.argv[1] if len(sys.argv) >= 2 and not sys.argv[1].startswith("--") else time.strftime("%Y%m%d")
    prev = None
    if "--prev" in sys.argv:
        prev = sys.argv[sys.argv.index("--prev") + 1]
    if "--t86-max-wait-min" in sys.argv:
        os.environ["TAIWAN_T86_MAX_WAIT_MIN"] = sys.argv[sys.argv.index("--t86-max-wait-min") + 1]
    w = west(date)
    t_start = time.time()

    print(f"===== 台股盘后 SOP  交易日 {date} ({w}) =====")
    print(f"data_dir={DATA}  t86_max_wait_min={_t86_max_wait_min()}")

    # Step1: TWSE 全量 (twse.py 拉 IND/MS/BFI82U/T86/MI_MARGN/FMTQIK)
    print("\n--- Step1 TWSE 官方全量 ---")
    sh([sys.executable, "collectors/twse.py", date], label="twse", must_succeed=True)
    # 补拉全档个股收盘 + TAIEX OHLC (twse.py 主端点外的两个)
    sh([sys.executable, "-c", _STEP1_EXTRA.format(date=date, w=w)], label="stock_all+ohlc", must_succeed=True)

    # Step1b: T86 个股法人明细 ~16:00-16:30 才发布, 若空则轮询等待
    print("\n--- Step1b T86 个股法人明细 ---")
    max_wait = _t86_max_wait_min()
    if max_wait <= 0:
        print("  t86_max_wait_min=0, 跳过等待 (历史日模式)")
    else:
        # attempts = ceil(max_wait / 5), at least 1
        attempts = max(1, (max_wait + 4) // 5)
        sh([sys.executable, "-c", _STEP1B_T86.format(
            date=date, w=w, attempts=attempts, interval=300)],
            label=f"t86_wait({max_wait}min)")

    # Step2: TAIFEX 期货 (今日, 可选前一交易日)
    print("\n--- Step2 TAIFEX 期货三大法人未平仓 ---")
    tf_args = [sys.executable, "collectors/taifex.py", f"{date[:4]}/{date[4:6]}/{date[6:8]}"]
    if prev:
        tf_args.append(f"{prev[:4]}/{prev[4:6]}/{prev[6:8]}")
    sh(tf_args, label="taifex", must_succeed=True)
    # 落 taifex_net_oi.json 供 analyze 读取
    sh([sys.executable, "-c", _STEP2_OI.format(w=w, prev=repr(prev))], label="taifex_net_oi", must_succeed=True)

    # Step3+4: 汇总校验 -> digest.json
    print("\n--- Step3/4 汇总 + 闭环校验 ---")
    sh([sys.executable, "lib/analyze.py", w], label="analyze", must_succeed=True)
    # 产物门禁
    digest_path = os.path.join(DATA, w, "digest.json")
    if not os.path.exists(digest_path):
        print(f"[ABORT] analyze 未产出 digest: {digest_path}", file=sys.stderr)
        sys.exit(2)

    # Step4b: 法人连续买卖超个股 (T86 回溯自算, 本地优先)
    print("\n--- Step4b 法人连续买卖超个股 (近10交易日) ---")
    sh([sys.executable, "lib/inst_streak.py", w, "10"], label="inst_streak")

    # Step4c: 生成次日盘前部署交接 (盘后不自带次日展望, 交接给次日早评)
    print("\n--- Step4c 盘前部署交接 handoff ---")
    sh([sys.executable, "lib/handoff.py", w], label="handoff")

    print(f"\n===== 数据层完成. digest: {DATA}/{w}/digest.json =====")
    print(f"[total] {_elapsed(t_start)}")
    print("下一步: generate_afterhours_report.py 调 compose_report 成稿。")


# --- inline subprocess scripts (kept as templates to avoid extra files) ---

_STEP1_EXTRA = """
from collectors.twse import fetch_json
import os
from lib.json_io import dump
d='{w}'
base=os.environ['TAIWAN_EQUITY_DATA']
os.makedirs(os.path.join(base,d), exist_ok=True)
for key,url in [
 ('twse_stock_all','https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date}&type=ALLBUT0999&response=json'),
 ('twse_taiex_ohlc','https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST?date={date}&response=json'),
]:
    try:
        j=fetch_json(url); dump(j, os.path.join(base,d,key+'.json'))
        print(f'  [OK] {{key}}')
    except Exception as e:
        print(f'  [FAIL] {{key}}: {{e}}')
        raise
"""

_STEP1B_T86 = """
from collectors.twse import fetch_json, build_url
import os, time
from lib.json_io import dump
base=os.environ['TAIWAN_EQUITY_DATA']
out=os.path.join(base,'{w}','twse_t86.json')
# already-fetched & fresh -> skip waiting
import json
try:
    j=json.load(open(out,encoding='utf-8'))
    if j.get('stat')=='OK' and j.get('data'):
        print(f'  T86 已存在且就绪: {{len(j["data"])}} 行, 跳过等待'); raise SystemExit(0)
except (OSError, ValueError, KeyError):
    pass
os.makedirs(os.path.join(base,'{w}'), exist_ok=True)
for attempt in range({attempts}):
    try:
        j = fetch_json(build_url('/fund/T86', {{'selectType':'ALLBUT0999'}}, '{date}'))
    except Exception:
        j = {{}}
    if j.get('stat') == 'OK' and j.get('data'):
        dump(j, out)
        print(f'  T86 就绪: {{len(j["data"])}} 行 (第{{attempt+1}}次)')
        break
    if attempt+1 < {attempts}:
        print(f'  T86 尚未发布, {{int({interval}/60)}}分钟后重试 (第{{attempt+1}}/{{attempts}})')
        time.sleep({interval})
else:
    print('  T86 等待超时, 静默降级(个股/连续买卖超将缺)')
"""

_STEP2_OI = """
from collectors.taifex import parse_tx_net_oi
import os
from lib.json_io import dump
base=os.environ['TAIWAN_EQUITY_DATA']
html=open(os.path.join(base,'{w}','taifex_futcontracts.html'),encoding='utf-8').read()
net,_=parse_tx_net_oi(html)
out={{'tx_net_oi':net,'foreign_net':net['外資']}}
prev={prev}
if prev:
    try:
        pw=f"{{prev[:4]}}-{{prev[4:6]}}-{{prev[6:8]}}"
        ph=open(os.path.join(base,pw,'taifex_futcontracts.html'),encoding='utf-8').read()
        pn,_=parse_tx_net_oi(ph); out['prev_foreign_net']=pn['外資']; out['foreign_net_change']=net['外資']-pn['外資']
    except Exception: pass
dump(out, os.path.join(base,'{w}','taifex_net_oi.json'))
print('  taifex_net_oi:',out)
"""


if __name__ == "__main__":
    main()
