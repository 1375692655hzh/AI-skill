#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Webhook push adapters: Bark / 企业微信群机器人 / Server酱.

All channels accept a plain-text message + optional title and POST once.
Configuration: config.push.{channel}.{key_env|webhook_env|...} from config.json.
Secrets are read from environment variables (never stored in config).
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests


@dataclass
class PushResult:
    ok: bool
    channel: str
    detail: str = ""
    dry_run: bool = False


def _resolve_env(name: Optional[str]) -> str:
    if not name:
        return ""
    return os.environ.get(name) or ""


def push_bark(
    text: str,
    cfg: dict,
    *,
    title: str = "HK IPO",
) -> PushResult:
    """Bark push. cfg: { base_url, key_env, sound, group }"""
    key = _resolve_env(cfg.get("key_env"))
    if not key:
        return PushResult(False, "bark", "BARK_KEY env not set")
    base = (cfg.get("base_url") or "https://api.day.app").rstrip("/")
    url = f"{base}/{key}"
    body = {
        "title": title,
        "body": text,
        "sound": cfg.get("sound", "alert"),
        "group": cfg.get("group", "HKIPO"),
    }
    try:
        r = requests.post(url, json=body, timeout=15)
        r.raise_for_status()
        return PushResult(True, "bark", f"{r.status_code}")
    except Exception as exc:  # noqa: BLE001
        return PushResult(False, "bark", str(exc))


def push_wx_work(text: str, cfg: dict, *, title: str = "HK IPO") -> PushResult:
    """企业微信群机器人 (markdown-limited). cfg: { webhook_env, mentioned_mobile_list }"""
    webhook = _resolve_env(cfg.get("webhook_env"))
    if not webhook:
        return PushResult(False, "wx_work", "WECOM_WEBHOOK env not set")
    # wx_work supports markdown message type
    md = f"## {title}\n\n{text}" if title else text
    body = {
        "msgtype": "markdown",
        "markdown": {"content": md, "mentioned_mobile_list": cfg.get("mentioned_mobile_list") or []},
    }
    try:
        r = requests.post(webhook, json=body, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("errcode") not in (0, None):
            return PushResult(False, "wx_work", f"errcode={data.get('errcode')} {data.get('errmsg')}")
        return PushResult(True, "wx_work", f"{r.status_code}")
    except Exception as exc:  # noqa: BLE001
        return PushResult(False, "wx_work", str(exc))


def push_serverchan(text: str, cfg: dict, *, title: str = "HK IPO") -> PushResult:
    """Server酱 Turbo. cfg: { key_env, channel }"""
    key = _resolve_env(cfg.get("key_env"))
    if not key:
        return PushResult(False, "serverchan", "SC_KEY env not set")
    url = f"https://sctapi.ftqq.com/{key}.send"
    body = {
        "title": title[:32],
        "desp": text,
        "channel": cfg.get("channel", "wechat"),
    }
    try:
        r = requests.post(url, json=body, timeout=15)
        r.raise_for_status()
        return PushResult(True, "serverchan", f"{r.status_code}")
    except Exception as exc:  # noqa: BLE001
        return PushResult(False, "serverchan", str(exc))


PUSHERS = {
    "bark": push_bark,
    "wx_work": push_wx_work,
    "serverchan": push_serverchan,
}


def push(
    text: str,
    push_cfg: dict,
    *,
    title: str = "HK IPO",
    log_path: Optional[Path] = None,
) -> PushResult:
    """Dispatch to the configured channel; honor dry_run."""
    channel = push_cfg.get("channel", "bark")
    dry_run = bool(push_cfg.get("dry_run", False))
    if dry_run:
        msg = f"[dry_run] {channel}\n--- title={title} ---\n{text}"
        print(msg)
        _log(log_path, msg)
        return PushResult(True, channel, "dry_run", dry_run=True)

    pusher = PUSHERS.get(channel)
    if not pusher:
        msg = f"unknown push channel: {channel}"
        print(msg, file=sys.stderr)
        _log(log_path, msg)
        return PushResult(False, channel, msg)

    res = pusher(text, push_cfg.get(channel) or {}, title=title)
    _log(log_path, f"[{res.channel}] ok={res.ok} {res.detail}\n---\n{text}")
    if not res.ok:
        print(f"[push FAIL {res.channel}] {res.detail}", file=sys.stderr)
    else:
        print(f"[push OK {res.channel}] {res.detail}")
    return res


def _log(log_path: Optional[Path], text: str) -> None:
    if not log_path:
        return
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"\n==== {datetime.now().isoformat(timespec='seconds')} ====\n")
            f.write(text)
            f.write("\n")
    except OSError:
        pass
