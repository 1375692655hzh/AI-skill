# 部署指南 — 港股新股 Skill

本 skill 可独立运行，适用于 Cursor / Codex / Claude Code / Hermes / Windows Task Scheduler / cron。流程对齐 HKEX 披露易 + Tiger JSON + AAStocks 三源采集。

---

## 1. 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.10+ |
| 网络 | 可访问 `www1.hkexnews.hk`、`hktrade.skytigris.com`、`hk.aastocks.com`（中国大陆可直连） |
| 依赖 | `pip install -r requirements.txt`（requests + beautifulsoup4 + pdfplumber） |
| Webhook | Bark / 企业微信 / Server酱（任选其一，提醒用） |

推送（Webhook）**默认 Bark**，可换企业微信或 Server酱；未配置时 `dry_run=true` 只打日志。

---

## 2. 安装（3 步）

### 步骤 1：复制目录

本 skill **自成一体**，复制整个文件夹即可：

```
~/skills/hkipo-update-skill/
```

默认 `data/state.db` 在本目录内，不依赖其他 skill。

### 步骤 2：安装依赖

```powershell
cd hkipo-update-skill
pip install -r requirements.txt
```

### 步骤 3：配置

```powershell
Copy-Item config.example.json config.json
```

编辑 `config.json`：

1. **push.channel**：选 `bark` / `wx_work` / `serverchan`（也可保持 `dry_run: true` 先不推）
2. **holidays**：港股额外假期 `YYYY-MM-DD`（HKEX 标准假期内置）
3. **llm***：可选，仅供每日摘要（提醒本身不用 LLM）

```powershell
# Bark
$env:BARK_KEY = "你的Bark key"

# 企业微信群机器人
$env:WECOM_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."

# Server酱
$env:SC_KEY = "你的SCKEY"
```

---

## 3. 运行（手动）

```powershell
# 每日主刷新（建议 07:30 后）
python scripts/run_update.py --config config.json

# 6 个提醒 slot（无事件静默退出 0）
python scripts/run_remind.py --config config.json --type cash_close      # 08:30
python scripts/run_remind.py --config config.json --type offer_open      # 09:00
python scripts/run_remind.py --config config.json --type margin_close    # 13:30
python scripts/run_remind.py --config config.json --type grey_open       # 16:00
python scripts/run_remind.py --config config.json --type refund          # 17:00
python scripts/run_remind.py --config config.json --type grey_close      # 18:15

# 每周清理（建议周日 03:00）
python scripts/cleanup_listed.py --config config.json
```

输出：

| 路径 | 说明 |
|------|------|
| `data/state.db` | SQLite，companies/events/daily_diff 三表 |
| `data/{YYYY-MM-DD}/` | 当日三源原始快照（14 天清理） |
| `output/{YYYY-MM-DD}/daily_digest.md` | 当日变动摘要（新招股/聆讯/递表/上市） |
| `output/{YYYY-MM-DD}/pushed_notifications.log` | webhook 推送审计 |
| `data/archive/{stock_code}.json` | 已上市公司归档（90 天后删除） |

---

## 4. 定时（Windows 任务计划）

### 方法 A：一键注册（推荐）

以管理员身份打开 PowerShell，运行：

```powershell
python scripts/register_scheduled_tasks.ps1 -SkillRoot "D:\AI-skills-git\hkipo\hkipo-update-skill"
```

会自动注册 8 个任务（1 update + 6 remind + 1 cleanup），任务名前缀 `HKIPO_`。

### 方法 B：手工注册

```powershell
$SkillRoot = "D:\AI-skills-git\hkipo\hkipo-update-skill"
$Python = "python"

# 07:30 主刷新（工作日）
schtasks /Create /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 07:30 /TN "HKIPO_Update" `
  /TR "$Python $SkillRoot\scripts\run_update.py --config $SkillRoot\config.json"

# 09:00 招股开始/上市提醒（工作日）
schtasks /Create /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 09:00 /TN "HKIPO_Remind_OfferOpen" `
  /TR "$Python $SkillRoot\scripts\run_remind.py --config $SkillRoot\config.json --type offer_open"

# 其余 5 个 slot 同理（08:30 cash_close / 13:30 margin_close / 16:00 grey_open / 17:00 refund / 18:15 grey_close）
# 周日 03:00 清理
schtasks /Create /SC WEEKLY /D SUN /ST 03:00 /TN "HKIPO_Cleanup" `
  /TR "$Python $SkillRoot\scripts\cleanup_listed.py --config $SkillRoot\config.json"
```

### macOS / Linux

```bash
crontab -e
# 07:30 工作日刷新；6 个提醒 slot；周日 03:00 清理
30 7 * * 1-5  cd /path/to/hkipo-update-skill && python scripts/run_update.py --config config.json >> output/cron.log 2>&1
30 8 * * 1-5  cd /path/to/hkipo-update-skill && python scripts/run_remind.py --config config.json --type cash_close >> output/cron.log 2>&1
# ... 同理 6 slot
0 3 * * 0     cd /path/to/hkipo-update-skill && python scripts/cleanup_listed.py --config config.json >> output/cron.log 2>&1
```

---

## 5. 文风

见 `STYLE.md`。推送文案一律结构化字段（公司/代码/业务/招股价/手数/截止/解冻/暗盘/上市），禁夸大词（神股/稳赚/必涨/打新），数字一律来自 DB，简报无则静默省略。

---

## 6. 常见问题

**Q: 提醒时间对不齐港股交易时间？**
→ 香港时间 = 北京时间（均 UTC+8），无需时区换算。

**Q: HKEX 没披露「融资截止(孖展)」？**
→ 融资截止由券商各自设定，HKEX 招股书不含。本 skill 默认按 `cash_close − 1 港股交易日` 推断，可在 `config.json` 的 `sources.tiger_json.margin_offset_days` 覆盖。

**Q: 港股交易日怎么算？**
→ `scripts/resolve_target_date.py` 内置 HKEX 标准假期（元旦/春节/清明/复活节/劳动节/佛诞/端午/特区成立/国庆/重阳/圣诞），`config.json.holidays` 可加额外假期。

**Q: 想看某日推送历史？**
→ `output/{YYYY-MM-DD}/pushed_notifications.log` 留全部 webhook 推送原文。

**Q: 想换富途/OpenD 当主源？**
→ 改 `config.json.sources.futu` 启用，或在 `scripts/collectors/` 加新 collector（接口对齐 `collect()` 返回 dict list）。
