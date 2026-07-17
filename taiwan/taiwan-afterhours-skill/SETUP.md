# 部署指南 — 台股盘后内参 Skill

本 skill 可独立运行，适用于 Cursor / Codex / Claude Code / Hermes / cron。  
流程对齐原 `taiwan-equity-daily` 盘后 SOP；成稿改为 OpenAI 兼容 LLM API（不再依赖本机 `claude -p`）。

---

## 1. 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.11+ |
| 网络 | 可访问 `www.twse.com.tw`、`www.taifex.com.tw` |
| LLM | MiniMax / OpenAI 等（`config.json`） |
| 依赖 | `pip install -r requirements.txt`（含 pandas） |

推送（WhatsApp）**不包含**；只产出文件。

---

## 2. 安装（3 步）

### 步骤 1：复制目录

本 skill **自成一体**，复制整个文件夹即可：

```
~/skills/taiwan-afterhours-skill/
```

默认数据在本目录 `data/`，成稿在 `output/`，不依赖其他 skill。

### 步骤 2：安装依赖

```bash
cd taiwan-afterhours-skill
pip install -r requirements.txt
```

### 步骤 3：配置

```bash
cp config.example.json config.json
```

编辑 `config.json`：

1. **LLM**：确认 `llm.api_key_env` 与环境变量名一致  
2. **data_dir**：默认 `data`（本目录内）  
3. **holidays**：台湾额外休市日 `YYYY-MM-DD`（台风假等）

```bash
# Linux / macOS
export MINIMAX_API_KEY="你的key"

# Windows PowerShell
$env:MINIMAX_API_KEY = "你的key"
```

---

## 3. 运行

```bash
# 今日盘后（台北时区交易日）
python scripts/generate_afterhours_report.py --config config.json

# 指定日期
python scripts/generate_afterhours_report.py --config config.json --force-date 2026-07-14

# 只出简报/prompt，不调 LLM
python scripts/generate_afterhours_report.py --config config.json --no-llm

# 已有 digest 时跳过采集
python scripts/generate_afterhours_report.py --config config.json --skip-collect
```

输出：

| 路径 | 说明 |
|------|------|
| `output/{date}/台股盘后内参_{date}.md` | 成稿 |
| `output/{date}/_数据简报_afterhours.md` | 审计用简报 |
| `data/{date}/digest.json` | 校验后数字源 |
| `data/{date}/盘前部署handoff_供次日早评.md` | 本目录内交接（仅本 skill 需要时） |

保底（钜亨、无 LLM）：

```bash
python run_fallback.py after 2026-07-14
```

---

## 4. 定时建议

台北时间交易日 **17:00** 后（可按 T86 延迟再跑）。Windows 用任务计划程序；macOS 可用 launchd/cron。

---

## 5. 文风

见根目录 `STYLE.md`。与盘前 skill **无强制耦合**；若同事只部署本目录即可单独跑盘后。
