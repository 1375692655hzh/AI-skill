#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Weekly cleanup — archive listed companies and prune stale snapshots.

Policy (all configurable via config.retention):
  1. companies WHERE status='listed' AND listing_date < today - grace_after_listing_days (30)
       → move to data/archive/{stock_code}.json, delete from companies + events
  2. data/archive/*.json WHERE mtime < today - archive_after_days (90) → delete
  3. data/{YYYY-MM-DD}/ WHERE date < today - raw_snapshot_days (14) → delete whole directory
  4. orphan events: events WHERE stock_code not in companies AND not in archive → delete

Run weekly (Sunday 03:00). Safe to run any time; idempotent.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from lib import db  # noqa: E402
from runtime_utils import configure_stdio, resolve_skill_paths  # noqa: E402


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run(config_path: Path) -> int:
    configure_stdio()
    config = load_config(config_path)
    _, _, data_dir, _, db_path = resolve_skill_paths(config_path, config)
    retention = config.get("retention") or {}
    grace = int(retention.get("grace_after_listing_days", 30))
    archive_days = int(retention.get("archive_after_days", 90))
    raw_days = int(retention.get("raw_snapshot_days", 14))

    today = date.today()
    cutoff_listed = (today - timedelta(days=grace)).isoformat()
    cutoff_archive = today - timedelta(days=archive_days)
    cutoff_snapshot = today - timedelta(days=raw_days)

    archive_dir = data_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    print(f"== hkipo cleanup today={today.isoformat()}")
    print(f"   archive listed before {cutoff_listed}  "
          f"(grace {grace}d)  prune archive before {cutoff_archive.isoformat()}  "
          f"(age {archive_days}d)  prune snapshots before {cutoff_snapshot.isoformat()} "
          f"(age {raw_days}d)")

    n_archived = n_archive_deleted = n_snap_deleted = n_orphan_events = 0

    with db.connect(db_path) as conn:
        # 1. Archive listed companies past grace period
        to_archive = db.list_listed_before(conn, cutoff_listed)
        archived_codes = set()
        for comp in to_archive:
            code = comp["stock_code"]
            target_path = archive_dir / f"{code}.json"
            target_path.write_text(
                json.dumps(comp, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            db.delete_company_and_events(conn, code)
            archived_codes.add(code)
            n_archived += 1
            print(f"   archived {code} → {target_path.name}")

        # 2. Prune archive files older than archive_after_days
        for f in archive_dir.glob("*.json"):
            try:
                mtime = date.fromtimestamp(f.stat().st_mtime)
            except OSError:
                continue
            if mtime < cutoff_archive:
                f.unlink(missing_ok=True)
                n_archive_deleted += 1
                print(f"   pruned archive {f.name} (mtime {mtime.isoformat()})")

        # 3. Prune raw snapshot dirs older than raw_snapshot_days
        if data_dir.is_dir():
            for d in data_dir.iterdir():
                if not d.is_dir() or d.name == "archive":
                    continue
                try:
                    d_date = date.fromisoformat(d.name)
                except ValueError:
                    continue
                if d_date < cutoff_snapshot:
                    shutil.rmtree(d, ignore_errors=True)
                    n_snap_deleted += 1
                    print(f"   pruned snapshot {d.name}")

        # 4. Orphan events: stock_code no longer in companies or archive
        existing_archive = {f.stem for f in archive_dir.glob("*.json")}
        rows = conn.execute("SELECT DISTINCT stock_code FROM events").fetchall()
        for r in rows:
            code = r["stock_code"]
            in_companies = conn.execute(
                "SELECT 1 FROM companies WHERE stock_code=? LIMIT 1", (code,)
            ).fetchone()
            if not in_companies and code not in existing_archive:
                cur = conn.execute(
                    "DELETE FROM events WHERE stock_code=?", (code,)
                )
                n_orphan_events += cur.rowcount
                print(f"   pruned orphan events for {code}")

    print(
        f"✅ cleanup done: archived={n_archived} archive_pruned={n_archive_deleted} "
        f"snapshots_pruned={n_snap_deleted} orphan_events_pruned={n_orphan_events}"
    )
    return 0


def main():
    ap = argparse.ArgumentParser(description="HK IPO weekly cleanup")
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()
    cfg = Path(args.config)
    if not cfg.is_file():
        alt = HERE.parent / "config.json"
        if alt.is_file():
            cfg = alt
        else:
            print(f"config not found: {args.config}", file=sys.stderr)
            sys.exit(2)
    sys.exit(run(cfg))


if __name__ == "__main__":
    main()
