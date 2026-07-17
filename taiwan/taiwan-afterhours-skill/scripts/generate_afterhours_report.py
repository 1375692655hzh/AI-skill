#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main entry: Taiwan after-hours depth report (collect -> digest -> LLM)."""
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


def generate(config_path: Path, force_date=None, no_llm: bool = False, skip_collect: bool = False):
    configure_stdio()
    config = load_config(config_path)
    skill_dir, workdir, data_dir, output_dir = resolve_skill_paths(config_path, config)
    data_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    os.environ["TAIWAN_EQUITY_ROOT"] = str(skill_dir)
    os.environ["TAIWAN_EQUITY_DATA"] = str(data_dir)
    os.environ["TAIWAN_EQUITY_REPORTS"] = str(output_dir)
    t86_max = int(config.get("t86_max_wait_min", 35))
    os.environ["TAIWAN_T86_MAX_WAIT_MIN"] = str(t86_max)
    os.chdir(skill_dir)

    holidays = config.get("holidays") or []
    target = resolve_target_date(force_date, holidays)
    prev = previous_business_day(target, holidays)
    date8 = target.strftime("%Y%m%d")
    prev8 = prev.strftime("%Y%m%d")
    digest = data_dir / target.isoformat() / "digest.json"

    print(f"== afterhours target={target} prev={prev}")
    print(f"   skill={skill_dir}")
    print(f"   data={data_dir}")
    print(f"   output={output_dir}")

    if not skip_collect:
        if digest.is_file() and not config.get("force_recollect"):
            print(f"digest 已存在, 跳过采集: {digest}")
        else:
            cmd = [sys.executable, "run_afterhours.py", date8, "--prev", prev8]
            print("$", " ".join(cmd))
            rc = subprocess.run(cmd, cwd=str(skill_dir), env=os.environ.copy()).returncode
            if rc != 0 or not digest.is_file():
                print("数据层失败", file=sys.stderr)
                return None
    elif not digest.is_file():
        print(f"缺少 digest: {digest}", file=sys.stderr)
        return None

    # digest 产物门禁：闭环校验全 PASS 才进 LLM（可 config 强制忽略）
    if digest.is_file():
        dj = json.loads(digest.read_text(encoding="utf-8"))
        failed = [c for c in (dj.get("checks") or []) if len(c) >= 3 and not c[2]]
        if failed and not config.get("allow_failed_checks"):
            print(f"[ABORT] digest 闭环校验未通过, 不进 LLM (config.allow_failed_checks=True 可强制):", file=sys.stderr)
            for c in failed:
                print(f"   FAIL {c[0]}: {c[1]}", file=sys.stderr)
            return None
        if failed:
            print(f"[WARN] digest 有失败校验, allow_failed_checks=True 继续: {failed}", file=sys.stderr)

    import compose_report

    out = compose_report.compose(
        "afterhours",
        target.isoformat(),
        llm_cfg=config.get("llm") or {},
        no_llm=no_llm,
    )
    return Path(out) if out else None


def main():
    ap = argparse.ArgumentParser(description="Generate Taiwan after-hours equity report")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--force-date", default=None, help="YYYY-MM-DD")
    ap.add_argument("--no-llm", action="store_true", help="Only build brief/prompt")
    ap.add_argument("--skip-collect", action="store_true", help="Reuse existing digest")
    args = ap.parse_args()
    cfg = Path(args.config)
    if not cfg.is_file():
        # allow running from repo with example
        alt = Path(__file__).resolve().parent.parent / "config.json"
        ex = Path(__file__).resolve().parent.parent / "config.example.json"
        if alt.is_file():
            cfg = alt
        elif ex.is_file():
            print("config.json 不存在, 请先: cp config.example.json config.json", file=sys.stderr)
            sys.exit(2)
        else:
            print(f"config not found: {args.config}", file=sys.stderr)
            sys.exit(2)
    path = generate(cfg, force_date=args.force_date, no_llm=args.no_llm, skip_collect=args.skip_collect)
    if not path:
        sys.exit(1)
    print(path)


if __name__ == "__main__":
    main()
