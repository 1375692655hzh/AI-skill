# Turkey Info Daily Report Skill

抓取 Info Yatırım **Günlük Bülten**（每日市场公告），生成**纯文字**中文每日市场分析报告。

## 开箱即用

| 必需 | 可选 |
|------|------|
| Python 3.9+ | Turkey-investment 项目（读本地缓存） |
| `pip install -r requirements.txt` | Cron / 推送（自行配置） |
| LLM API Key（默认 `MINIMAX_API_KEY`） | |
| 复制本目录 + `config.json` | |

**不需要** Turkey-investment 主项目，direct 抓取可独立运行。

## 快速开始

```bash
cd turkey-info-daily-report-skill
pip install -r requirements.txt
export MINIMAX_API_KEY="your-key"    # PowerShell: $env:MINIMAX_API_KEY="your-key"
python scripts/generate_info_daily_report.py --config config.json
```

输出：`output/{date}_info_daily_report_zh.txt`

## 推荐执行时间

源站发布：TR ~11:00 / 北京 ~16:00

| 北京时间 | 动作 |
|----------|------|
| **16:20** | 首发 |
| 16:30–17:10 | 每 10 分钟重试（共 6 次） |
| **20:00** | 兜底 |
| 周末/土节假日 | 跳过 |

## 可选：Turkey-investment 对接

```json
"sources": {
  "info_daily": {
    "use_project_fetcher": true,
    "project_path": "/path/to/Turkey-investment"
  }
}
```

## 文档

- `SKILL.md` — Agent 调用说明（含完整时间表）
- `SETUP.md` — 部署指南 + Cron 示例
