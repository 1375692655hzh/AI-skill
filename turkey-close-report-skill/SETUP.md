# 部署指南 — 土耳其股市收评 Skill

本 skill 可独立运行，**不需要** Turkey-investment 主项目。适用于 Cursor、Codex、Claude Code、Hermes、OpenClaw、WorkBuddy 等支持 Agent Skill 的环境。

---

## 1. 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.9+ |
| 网络 | 能访问 `bloomberght.com`、`paraborsa.com`、`infoyatirim.com` |
| LLM API | MiniMax / OpenAI 等（需能读土耳其语、写中文） |

---

## 2. 安装（3 步）

### 步骤 1：复制 skill 目录

将整个 `turkey-close-report-skill` 文件夹放到任意位置，例如：

```
~/skills/turkey-close-report-skill/
```

### 步骤 2：安装 Python 依赖

```bash
cd turkey-close-report-skill
pip install -r requirements.txt
```

### 步骤 3：配置

```bash
cp config.example.json config.json
```

编辑 `config.json` 确认 LLM 配置，设置 API Key：

```bash
# Linux / macOS
export MINIMAX_API_KEY="你的key"

# Windows PowerShell
$env:MINIMAX_API_KEY = "你的key"
```

默认 `workdir: "."`，输出和缓存都在 skill 目录内，无需改路径。

---

## 3. 运行

在 **skill 目录内** 执行：

```bash
# 生成今日收评
python scripts/generate_close_report.py --config config.json

# 指定日期
python scripts/generate_close_report.py --config config.json --force-date 2026-07-14

# 只生成 prompt（不调 LLM）
python scripts/generate_close_report.py --config config.json --no-llm
```

输出文件：

| 文件 | 说明 |
|------|------|
| `output/{日期}_close_report_zh.txt` | 完整收评 |
| `output/{日期}_close_report_brief_zh.txt` | 结构化简报（汉字+中文标点 400–500 字，个股每只一行） |

关闭简报：`config.json` 中设 `"brief": {"enabled": false}`。

---

## 4. 在 Agent 中使用

1. 将 skill 目录加入 agent 的 skill 搜索路径
2. Agent 加载 `SKILL.md`（触发词：土耳其收评 / close report）
3. Agent 执行上述 Python 命令
4. 读取 `output/` 下的成品文件

| 平台 | 放置位置 |
|------|---------|
| Cursor / Codex | `~/.cursor/skills/` 或 `.cursor/skills/` |
| Claude Code | `.claude/skills/` |
| Hermes | skill 目录 + cron 配置 |
| OpenClaw / WorkBuddy | 各平台 skill 目录 |

---

## 5. 目录结构

```
turkey-close-report-skill/
├── SKILL.md
├── SETUP.md                 # 本文件
├── config.json / config.example.json
├── requirements.txt
├── scripts/
├── templates/
├── references/
├── output/                  # 成品（自动创建）
└── .cache/                  # 缓存（自动创建）
```

---

## 6. 常见问题

**Q: 报错 "closing review not found"**
→ 北京时间 23:30 后再运行（等土耳其收盘文章发布）。

**Q: 缓存日期错位**
→ 删除 `.cache/turkey-close-report/*_{date}.*` 后重试；脚本已内置日期校验。

**Q: MiniMax 输出含 thinking 块**
→ `call_llm.py` 已自动禁用 thinking；确认使用 MiniMax-M3。

**Q: 成品出现券商/平台名称**
→ 脚本会自动重试；若仍失败，查看 `.cache/close_raw_output_*.txt` 调试。

---

## 7. 推荐运行时间

**北京时间 23:30+**（土耳其收盘后），此时 BloombergHT 详细收盘和券商评论均已发布。
