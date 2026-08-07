---
name: hkipo-update-skill
description: Use when generating a daily Hong Kong IPO (港股新股) update and event reminders — HKEX 多源（appindex JSON + 新上市信息页 + 招股文件页 + 招股书 PDF）作为金标准，Tiger JSON 字段补充，按 6 个时间点查库命中事件才推 webhook（Bark/企业微信/Server酱）。判定逻辑对齐 HKIPO 项目。
version: 1.1.0
author: AI-skills-git
license: MIT
metadata:
  hermes:
    tags: [hongkong, hkex, ipo, 港股新股, 招股, 暗盘, 聆讯, 递表, listing]
---

# HK IPO Update & Reminder Skill

## Overview

Standalone skill covering the full Hong Kong IPO lifecycle: 新递表 / 新聆讯 / 新招股 / 招股状态 / 暗盘 / 上市 / 资金解冻。**判定逻辑完全对齐 HKIPO 项目（`D:\AI项目\HKIPO`）**——HKEX 官方源作为金标准，第三方源（Tiger / AAStocks）只做字段补充。

Pipeline:
1. **07:30 daily** — refresh from 4 HKEX sources + Tiger JSON + AAStocks, write to local SQLite `state.db`, compute `daily_diff`
2. **6 reminder slots** (08:30 / 09:00 / 13:30 / 16:00 / 17:00 / 18:15) — query DB, only push webhook when an event actually fires today
3. **03:00 Sundays** — archive listed companies, prune stale snapshots

**No event = no push.** Empty slots exit 0 silently. The skill only emits a webhook when an actual event (offer open, cash close, margin close, refund, grey open/close, listing) lands on `today`.

## When to Use

- **Recommended**: 每交易日 07:30 后跑主刷新；提醒 slot 由外部 cron/Windows Task Scheduler 触发。
- Keywords: 港股新股 / 港股IPO / 招股 / 暗盘 / 上市 / HK IPO / hkex ipo。

## Inputs

1. Python 3.10+ and `requirements.txt`
2. Network access to `www1.hkexnews.hk`, `www2.hkexnews.hk`, `hktrade.skytigris.com`, `hk.aastocks.com`（在中国大陆均可直连，无需 VPN）
3. Optional webhook key (Bark / 企业微信 / Server酱) via env var
4. Optional LLM API via `config.json`（仅供每日摘要，提醒本身不用 LLM）

Self-contained: `data/`（含 `state.db`）和 `output/` 默认在本 skill 目录内，无需其他 skill。

## Outputs

- `data/state.db` — SQLite（companies / events / daily_diff 三表，唯一持久层）
- `data/{YYYY-MM-DD}/` — 当日多源原始快照（保留 14 天）
- `data/archive/{stock_code}.json` — 已上市公司归档（满 90 天删除）
- `output/{YYYY-MM-DD}/daily_digest.md` — 当日变动摘要（新招股 / 新聆讯 / 新递表 / 新上市）
- `output/{YYYY-MM-DD}/pushed_notifications.log` — 推送审计（每次 webhook 留痕）

## Run Flow

三个子命令（外部调度器调用）：

```bash
# 1. 每日主刷新（07:30）
python scripts/run_update.py --config config.json

# 2. 提醒（每个时间点一条 cron 调用一次）
python scripts/run_remind.py --config config.json --type cash_close
python scripts/run_remind.py --config config.json --type offer_open
python scripts/run_remind.py --config config.json --type margin_close
python scripts/run_remind.py --config config.json --type grey_open
python scripts/run_remind.py --config config.json --type refund
python scripts/run_remind.py --config config.json --type grey_close

# 3. 每周清理（周日 03:00）
python scripts/cleanup_listed.py --config config.json
```

`run_update.py` 内部步骤（5 源 + PDF）：
1. Resolve 港股交易日（HKEX 假期表 + config holidays）
2. `collectors/hkex_appindex.py` — HKEX 4 个 JSON（递表/PHIP/已上市/退回）；从 `ls[]` 抽 `ap_date`/`phip_date` 里程碑
3. `collectors/hkex_new_listings.py` — **HKEX 新上市信息页（主板+GEM）+ 招股文件页（predefineddoc）并集 = in_offer 主判定**
4. `collectors/tiger_ipo.py` — 字段补充（招股价/手数/截止/上市/暗盘时间）
5. `collectors/aastocks_ipo.py` — 交叉校验
6. `collectors/hkex_prospectus_pdf.py` — 招股书 PDF 預期時間表 regex（20+ 模式 + OCR 归一化，移植自 HKIPO `ipo_lifecycle.py`）
7. `lib/normalize.py` — 多源字段归一 → UPSERT `companies`（status 按 lifecycle rank 优先级合并）
8. `lib/compute_events.py` — 算 7 类事件日期（margin=自然日-1 / grey=交易日-1 / refund=交易日-2）→ INSERT `events`
9. 计算 `daily_diff` → 写 `output/{date}/daily_digest.md`

`run_remind.py` 内部步骤：
1. `SELECT * FROM events WHERE event_date=today AND event_type IN slot AND fired_at IS NULL`
2. 无命中 → exit 0（不推）
3. 有命中 → 渲染 `templates/reminder_{type}.txt` → `push_webhook.py` → `UPDATE events SET fired_at=now`

## Reminder Slot Mapping

| Cron 时间 (HKT/BJ) | event_type | 触发条件 |
|---|---|---|
| 08:30 | `cash_close` | 今日=现金(eIPO/白表)截止日 |
| 09:00 | `offer_open` + `listing` | 今日=招股开始日 / 今日=上市日 |
| 13:30 | `margin_close` | 今日=融资(孖展)截止日 |
| 16:00 | `grey_open` | 今日=暗盘日（暗盘 16:15 开始） |
| 17:00 | `refund` | 今日=资金解冻日 |
| 18:15 | `grey_close` | 今日=暗盘日（暗盘 18:30 结束） |

## Configuration

See `config.example.json`. Critical keys:

| Key | Purpose |
|-----|---------|
| `db_path` | SQLite 路径（默认 `data/state.db`） |
| `sources.*` | 5 源开关 + endpoint（hkex_appindex / hkex_new_listings / tiger_json / aastocks / hkex_pdf） |
| `push.channel` | `bark` / `wx_work` / `serverchan` |
| `push.{channel}.key_env` / `webhook_env` | webhook 凭据环境变量名 |
| `push.silent_when_no_event` | 无事件时静默退出（默认 true） |
| `push.dry_run` | 只打日志不发，调试用 |
| `schedule.*` | 6 个提醒 slot + update/cleanup 时间，供文档/校验 |
| `retention.*` | 清理保留策略（原始 14 天 / 上市后 30 天归档 / 归档 90 天删除） |
| `holidays` | 港股额外假期 `YYYY-MM-DD`（HKEX 标准假期内置） |

## Data Discipline（对齐 HKIPO 项目）

- HKEX appindex JSON 是 新递表 / 聆讯(PHIP) / 上市 的**金标准**
- **HKEX 新上市信息页 + 招股文件页是「招股」判定的主源**（覆盖「已发招股书但申购未开始」公司，比 Tiger `OPEN` 更早）
- Tiger JSON 是 招股价 / 板数 / 截止日期 / 暗盘时间 的**字段补充源**
- AAStocks 做 正在招股 / 擬上市 / 暗盘价 的**交叉校验**
- 融资截止(孖展) = cash_close − 1 **自然日**（港股惯例，HKIPO `ipo_calendar.py` 同口径）
- 暗盘日期 = 上市日 − 1 港股交易日，时间固定 16:15–18:30 HKT
- 资金解冻 = listing − 2 港股交易日（当 PDF 没明示时）
- 任一源失败 → 静默降级（不阻断主流程），在 daily_digest.md 标注降级项
- 数字一律来自 DB，简报无则静默省略，禁编造、禁占位

Details: `references/data_sources.md` + `STYLE.md`。
