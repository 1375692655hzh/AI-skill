# 部署指南 — Turkey Info Daily Report Skill

本 skill **开箱即用**，可独立运行，**不需要** Turkey-investment 主项目。适用于 Cursor、Codex、Claude Code、Hermes、OpenClaw、WorkBuddy 等支持 Agent Skill 的环境。

---

## 开箱即用清单

给别人时，确认以下 4 项即可：

| # | 项目 | 说明 |
|---|------|------|
| 1 | 复制整个 skill 目录 | 含 `SKILL.md`、`config.json`、`scripts/`、`templates/` |
| 2 | `pip install -r requirements.txt` | 仅 4 个依赖：requests、beautifulsoup4、lxml、feedparser |
| 3 | 设置 LLM API Key | 默认 `MINIMAX_API_KEY`；可在 `config.json` 改 provider |
| 4 | 在 skill 目录内运行脚本 | 输出自动写到 `output/`，缓存到 `.cache/` |

**不需要**：Turkey-investment 项目、数据库、额外推送服务。

**可选增强**：本地有 Turkey-investment 且已抓取过时，设 `use_project_fetcher: true` 可读已落盘 Markdown（质量更稳）。

---

## 1. 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.9+ |
| 网络 | 能访问 `infoyatirim.com`、`cdn.infoyatirim.com` |
| LLM API | MiniMax / OpenAI 等（需能读土耳其语、写中文） |

---

## 2. 安装（3 步）

### 步骤 1：复制 skill 目录

```
~/skills/turkey-info-daily-report-skill/
```

### 步骤 2：安装依赖

```bash
cd turkey-info-daily-report-skill
pip install -r requirements.txt
```

### 步骤 3：配置 API Key

仓库已附带 `config.json`，一般无需改路径。只需设置 Key：

```bash
# Linux / macOS
export MINIMAX_API_KEY="你的key"

# Windows PowerShell
$env:MINIMAX_API_KEY = "你的key"
```

首次部署可复制模板：`cp config.example.json config.json`

---

## 3. 运行

在 **skill 目录内** 执行：

```bash
# 生成今日每日分析
python scripts/generate_info_daily_report.py --config config.json

# 指定日期
python scripts/generate_info_daily_report.py --config config.json --force-date 2026-07-14

# 只生成 prompt（不调 LLM，用于调试）
python scripts/generate_info_daily_report.py --config config.json --no-llm
```

输出：`output/{日期}_info_daily_report_zh.txt`

---

## 4. 推荐执行时间（Cron）

土耳其时间 TR = UTC+3（无夏令时）；北京 = UTC+8。

| 项目 | 时间 |
|------|------|
| Info Günlük 源站发布 | TR ~11:00 / 北京 ~16:00 |
| **推荐 Cron 首发** | **北京时间 16:20** |
| 重试策略 | 每 10 分钟 × 6 次（至 17:10） |
| 兜底 | 北京时间 20:00 再 1 次 |
| 休市 | 周六、周日、土耳其公共假期跳过 |

### Cron 示例（Linux crontab，北京时间）

```cron
# 交易日 16:20 首发 + 10 分钟重试 × 5
20 16 * * 1-5 cd /path/to/turkey-info-daily-report-skill && python scripts/generate_info_daily_report.py --config config.json
30 16 * * 1-5 cd /path/to/turkey-info-daily-report-skill && python scripts/generate_info_daily_report.py --config config.json
40 16 * * 1-5 cd /path/to/turkey-info-daily-report-skill && python scripts/generate_info_daily_report.py --config config.json
50 16 * * 1-5 cd /path/to/turkey-info-daily-report-skill && python scripts/generate_info_daily_report.py --config config.json
0  17 * * 1-5 cd /path/to/turkey-info-daily-report-skill && python scripts/generate_info_daily_report.py --config config.json
10 17 * * 1-5 cd /path/to/turkey-info-daily-report-skill && python scripts/generate_info_daily_report.py --config config.json
# 20:00 兜底
0  20 * * 1-5 cd /path/to/turkey-info-daily-report-skill && python scripts/generate_info_daily_report.py --config config.json
```

> 注意：cron 按**服务器本地时区**执行。若服务器是 UTC，需换算为 UTC+8。

### Hermes / Agent 调度建议

- 仅在 `reason=not_found`（公告未发布）时继续重试
- 周末/节假日（`config.json` → `holidays`）不要重试

---

## 5. 可选：对接 Turkey-investment 项目

若本地有已抓取的报告，编辑 `config.json`：

```json
{
  "sources": {
    "info_daily": {
      "use_project_fetcher": true,
      "project_path": "/path/to/Turkey-investment"
    }
  }
}
```

优先读取 `reports/turkey-market-reports/{date}/` 下已落盘 Markdown。

---

## 6. 在 Agent 中使用

| 平台 | 放置位置 |
|------|---------|
| Cursor / Codex | `~/.cursor/skills/` 或项目 `.cursor/skills/` |
| Hermes | skill 目录 + cron 引用 `SKILL.md` |
| OpenClaw / WorkBuddy | 个人 skill 目录 |

触发：`/turkey-info-daily-report-skill` 或关键词「Info 日报」「每日市场分析」。

---

## 7. 常见问题

**Q: 16:00 运行报 not_found？**
→ 正常，公告通常 16:00–16:15 北京才上线，等 16:20 首发档。

**Q: 今天是土耳其假期，没有生成？**
→ 正常；可用 `--force-date` 指定历史交易日。

**Q: Windows 乱码？**
→ 脚本已内置 UTF-8；可额外设 `$env:PYTHONIOENCODING = "utf-8"`。

**Q: 需要推送 WhatsApp？**
→ 本 skill 只写文件；推送由调用方在 `output/` 读取后自行发送。
