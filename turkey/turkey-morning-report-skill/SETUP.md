# 部署指南 — 土耳其股市早报 Skill

本 skill 可独立运行，**不需要** Turkey-investment 主项目。适用于 Cursor、Codex、Claude Code、Hermes、OpenClaw、WorkBuddy 等支持 Agent Skill 的环境。

---

## 1. 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.9+ |
| 网络 | 能访问 `bloomberght.com`（土耳其财经网站） |
| LLM API | MiniMax / OpenAI 等（需能读土耳其语、写中文） |

---

## 2. 安装（3 步）

### 步骤 1：复制 skill 目录

将整个 `turkey-morning-report-skill` 文件夹放到任意位置，例如：

```
~/skills/turkey-morning-report-skill/
```

### 步骤 2：安装 Python 依赖

在 skill 目录下执行：

```bash
cd turkey-morning-report-skill
pip install -r requirements.txt
```

### 步骤 3：配置

```bash
cp config.example.json config.json
```

编辑 `config.json`：

1. **LLM**：默认已配置 MiniMax，确认 `llm.api_key_env` 与你的 Key 环境变量名一致
2. **路径**：默认 `workdir: "."` 表示输出写在 skill 目录内，一般无需修改
3. **可选**：若你有 Turkey-investment 主项目，可把 `sources.bloomberght_closing.use_project_fetcher` 设为 `true`，并设置 `workdir` 为该项目路径

设置 API Key：

```bash
# Linux / macOS
export MINIMAX_API_KEY="你的key"

# Windows PowerShell
$env:MINIMAX_API_KEY = "你的key"
```

---

## 3. 运行

在 **skill 目录内** 执行：

```bash
# 生成今日早报
python scripts/generate_briefing.py --config config.json

# 指定日期
python scripts/generate_briefing.py --config config.json --force-date 2026-07-14

# 只生成 prompt（不调 LLM，用于调试）
python scripts/generate_briefing.py --config config.json --no-llm
```

输出文件：

| 文件 | 说明 |
|------|------|
| `output/{日期}_daily_briefing_zh.txt` | 完整早评 |
| `output/{日期}_daily_briefing_brief_zh.txt` | 结构化简报（汉字+中文标点 200–520 字，个股每只一行） |

关闭简报：`config.json` 中设 `"brief": {"enabled": false}`。

---

## 4. 在 Agent 中使用

### 通用流程

1. 将 skill 目录加入 agent 的 skill 搜索路径
2. Agent 加载 `SKILL.md`（触发词：土耳其早报 / morning briefing）
3. Agent 执行上述 Python 命令
4. 读取 `output/` 下的成品文件

### 各平台

| 平台 | 放置位置 | 说明 |
|------|---------|------|
| **Cursor / Codex** | `~/.cursor/skills/` 或项目 `.cursor/skills/` | 需 terminal 权限 |
| **Claude Code** | 项目 `.claude/skills/` | 同上 |
| **Hermes** | skill 目录 + `config.yaml` 引用 | 可配 cron 定时 |
| **OpenClaw** | skill 注册目录 | 按 SKILL.md 流程执行 |
| **WorkBuddy** | 个人 skill 目录 | 加载 SKILL.md 后调脚本 |

---

## 5. 目录结构

```
turkey-morning-report-skill/
├── SKILL.md                 # Agent 指令（必需）
├── SETUP.md                 # 本文件
├── README.md / QUICKSTART.md
├── config.json              # 你的配置（勿提交 API Key）
├── config.example.json      # 配置模板
├── requirements.txt         # Python 依赖
├── scripts/                 # 执行脚本
├── templates/               # Prompt 模板
├── references/              # 参考文档
├── output/                  # 成品输出（自动创建）
└── .cache/                  # 抓取缓存（自动创建）
```

---

## 6. 常见问题

**Q: 报错 "Environment variable MINIMAX_API_KEY is not set"**
→ 设置环境变量后重试。

**Q: Windows 控制台乱码**
→ 脚本已内置 UTF-8 修复；若仍有问题，执行 `$env:PYTHONIOENCODING = "utf-8"`。

**Q: BloombergHT 抓取失败**
→ 检查网络；北京时间 14:30 后数据更完整。

**Q: 今天是土耳其假期，没有生成**
→ 正常行为；可用 `--force-date` 指定前一交易日。

**Q: 需要自动搜国际新闻？**
→ 将 `sources.news.mode` 改为 `"api"` 并配置 `sources.news.api`；或让 agent 预先写入 `.cache/news_{date}.json`。

---

## 7. 推荐运行时间

**北京时间 14:30**（土耳其开盘前），此时 BloombergHT 当日新闻已更新。
