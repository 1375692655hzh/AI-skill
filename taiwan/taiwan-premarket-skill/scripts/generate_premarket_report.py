#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main entry: Taiwan premarket report (self-contained; auto-fetches T-1 inventory if missing)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from resolve_target_date import previous_business_day, resolve_target_date
from runtime_utils import configure_stdio, resolve_skill_paths


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _has_inventory(data_dir: Path, day) -> bool:
    """True if previous trading day has usable stock_all (real session)."""
    sa = data_dir / day.isoformat() / "twse_stock_all.json"
    return sa.is_file() and sa.stat().st_size > 1000


def ensure_prev_inventory(skill_dir: Path, data_dir: Path, prev, holidays) -> bool:
    """
    Standalone premarket: if T-1 inventory missing, run the *lightweight* after-hours
    collect (collect_t1_lite.py) inside this skill — not the full SOP.
    """
    if _has_inventory(data_dir, prev):
        print(f"T-1 库存已存在: {prev}")
        return True
    prev_prev = previous_business_day(prev, holidays)
    date8 = prev.strftime("%Y%m%d")
    prev8 = prev_prev.strftime("%Y%m%d")
    print(f"T-1 库存缺失, 本 skill 内轻量补采 (collect_t1_lite): {prev} (prev={prev_prev})")
    cmd = [sys.executable, "collect_t1_lite.py", date8, prev8]
    print("$", " ".join(cmd))
    rc = subprocess.run(cmd, cwd=str(skill_dir), env=os.environ.copy()).returncode
    if rc != 0 or not _has_inventory(data_dir, prev):
        print("T-1 轻量补采失败（盘前将尽量降级继续）", file=sys.stderr)
        return False
    return True


def generate(config_path: Path, force_date=None, no_llm: bool = False, skip_collect: bool = False):
    configure_stdio()
    config = load_config(config_path)
    skill_dir, workdir, data_dir, output_dir = resolve_skill_paths(config_path, config)
    data_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    os.environ["TAIWAN_EQUITY_ROOT"] = str(skill_dir)
    os.environ["TAIWAN_EQUITY_DATA"] = str(data_dir)
    os.environ["TAIWAN_EQUITY_REPORTS"] = str(output_dir)
    futu = (config.get("opend") or {}).get("futu_python")
    if futu and Path(futu).expanduser().exists():
        os.environ["TAIWAN_FUTU_PYTHON"] = str(Path(futu).expanduser())
        print(f"[premarket] OpenD python: {futu}")
    else:
        print("[premarket] OpenD 未配置或路径不存在, ADR/费半层将降级 (cnyes 叙事层仍可用)")
    os.chdir(skill_dir)

    holidays = config.get("holidays") or []
    target = resolve_target_date(force_date, holidays)
    prev = previous_business_day(target, holidays)
    digest = data_dir / target.isoformat() / "premarket_digest.json"

    print(f"== premarket target={target} (standalone, data={data_dir})")

    if not skip_collect:
        ensure_prev_inventory(skill_dir, data_dir, prev, holidays)
        if digest.is_file() and not config.get("force_recollect"):
            print(f"premarket digest 已存在, 跳过盘前采集: {digest}")
        else:
            cmd = [sys.executable, "run_premarket.py", target.isoformat(), prev.isoformat()]
            print("$", " ".join(cmd))
            rc = subprocess.run(cmd, cwd=str(skill_dir), env=os.environ.copy()).returncode
            if rc != 0 or not digest.is_file():
                print("盘前数据层失败", file=sys.stderr)
                return None
    elif not digest.is_file():
        print(f"缺少 premarket_digest: {digest}", file=sys.stderr)
        return None

    import compose_report

    out = compose_report.compose(
        "premarket",
        target.isoformat(),
        llm_cfg=config.get("llm") or {},
        no_llm=no_llm,
    )
    return Path(out) if out else None


def main():
    ap = argparse.ArgumentParser(description="Generate Taiwan premarket equity report (standalone)")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--force-date", default=None)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--skip-collect", action="store_true")
    args = ap.parse_args()
    cfg = Path(args.config)
    if not cfg.is_file():
        print("请先: cp config.example.json config.json", file=sys.stderr)
        sys.exit(2)
    path = generate(cfg, force_date=args.force_date, no_llm=args.no_llm, skip_collect=args.skip_collect)
    if not path:
        sys.exit(1)
    print(path)


if __name__ == "__main__":
    main()
