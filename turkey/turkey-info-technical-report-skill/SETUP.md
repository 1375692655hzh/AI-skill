# 部署指南 — Turkey Info Technical Report Skill

本 skill **开箱即用**，默认 direct 抓取可独立运行。适用于 Cursor、Codex、Claude Code、Hermes、OpenClaw、WorkBuddy 等 Agent 环境。

---

## 开箱即用清单

给别人时，确认以下 4 项即可：

| # | 项目 | 说明 |
|---|------|------|
| 1 | 复制整个 skill 目录 | 含 `SKILL.md`、`config.json`、`scripts/`、`templates/` |
| 2 | `pip install -r requirements.txt` | requests、beautifulsoup4、lxml、feedparser |
| 3 | 设置 LLM API Key | 默认 `MINIMAX_API_KEY`；建议 `max_tokens ≥ 12000` |
| 4 | 在 skill 目录内运行脚本 | 输出到 `output/`，缓存到 `.cache/` |

**不需要**：Turkey-investment 项目（direct 模式自带抓取）。

**推荐增强**：有 Turkey-investment 本地缓存时，设 `use_project_fetcher: true` 读取 Markdown 表格，生成质量更好。

---

## 1. 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.9+ |
| 网络 | 能访问 `infoyatirim.com`、`cdn.infoyatirim.com` |
| LLM API | MiniMax / OpenAI 等（`max_tokens` 建议 ≥ 12000，表格较长） |

---

## 2. 安装（3 步）

### 步骤 1：复制 skill 目录

```
~/skills/turkey-info-technical-report-skill/
```

### 步骤 2：安装依赖

```bash
cd turkey-info-technical-report-skill
pip install -r requirements.txt
```

### 步骤 3：配置 API Key

```bash
export MINIMAX_API_KEY="你的key"          # Linux/macOS
$env:MINIMAX_API_KEY = "你的key"          # PowerShell
```

---

## 3. 运行

```bash
python scripts/generate_info_technical_report.py --config config.json
python scripts/generate_info_technical_report.py --config config.json --force-date 2026-07-09
python scripts/generate_info_technical_report.py --config config.json --no-llm
```

输出：`output/{日期}_info_technical_report_zh.txt`

---

## 4. 推荐执行时间（Cron）

土耳其时间 TR = UTC+3（无夏令时）；北京 = UTC+8。

| 项目 | 时间 |
|------|------|
| Info Teknik 源站发布 | TR ~12:00 / 北京 ~17:00 |
| **推荐 Cron 首发** | **北京时间 17:20** |
| 重试策略 | 每 10 分钟 × 6 次（至 18:10） |
| 兜底 | 北京时间 20:00 再 1 次 |
| 休市 | 周六、周日、土耳其公共假期跳过 |

### Cron 时间点（北京时间，交易日）

```
17:20, 17:30, 17:40, 17:50, 18:00, 18:10  → 首发循环
20:00                                       → 兜底
```

### Cron 示例（Linux crontab）

```cron
20 17 * * 1-5 cd /path/to/turkey-info-technical-report-skill && python scripts/generate_info_technical_report.py --config config.json
30 17 * * 1-5 cd /path/to/turkey-info-technical-report-skill && python scripts/generate_info_technical_report.py --config config.json
40 17 * * 1-5 cd /path/to/turkey-info-technical-report-skill && python scripts/generate_info_technical_report.py --config config.json
50 17 * * 1-5 cd /path/to/turkey-info-technical-report-skill && python scripts/generate_info_technical_report.py --config config.json
0  18 * * 1-5 cd /path/to/turkey-info-technical-report-skill && python scripts/generate_info_technical_report.py --config config.json
10 18 * * 1-5 cd /path/to/turkey-info-technical-report-skill && python scripts/generate_info_technical_report.py --config config.json
0  20 * * 1-5 cd /path/to/turkey-info-technical-report-skill && python scripts/generate_info_technical_report.py --config config.json
```

> cron 按服务器本地时区执行；UTC 服务器需换算。

### Hermes / Agent 调度建议

- 仅在公告未发布时重试；周末/节假日不重试
- 单只股票技术查询用 `bist-technical-kb`，本 skill 是全市场表格快照

---

## 5. 推荐：启用 Turkey-investment 抓取器

```json
{
  "sources": {
    "info_technical": {
      "use_project_fetcher": true,
      "project_path": "/path/to/Turkey-investment"
    }
  }
}
```

优先读取 `reports/turkey-market-reports/{date}/*_infoyatirim_technical_bulletin.md`（含完整 Pivot/RSI/CCI 表格）。

---

## 6. 在 Agent 中使用

触发：`/turkey-info-technical-report-skill` 或关键词「技术分析」「Teknik Bülten」。

---

## 7. 常见问题

**Q: 17:00 运行报 not_found？**
→ 正常，等 17:20 首发档。

**Q: 表格被截断？**
→ 将 `config.json` 中 `llm.max_tokens` 调到 12000+。

**Q: 和每日报告 skill 的区别？**
→ 每日报告偏文字段落；本 skill 偏 Markdown 表格（技术位、超买超卖、个股 Pivot）。
