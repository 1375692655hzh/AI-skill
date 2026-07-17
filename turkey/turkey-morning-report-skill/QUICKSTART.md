# 土耳其股市早报 Skill — 快速开始

## 一句话介绍

自动抓取 BloombergHT 土耳其市场数据 + 国际财经新闻，生成中文早报。

---

## 安装

### 1. 依赖

```bash
pip install -r requirements.txt
```

或：

```bash
pip install requests beautifulsoup4 feedparser
```

### 2. 配置 LLM API

编辑 `config.json`，设置你的 LLM API：

**方案 A：MiniMax（推荐国内用户）**

```json
{
  "llm": {
    "provider": "minimax",
    "model": "MiniMax-M3",
    "api_key_env": "MINIMAX_API_KEY",
    "base_url": "https://api.minimaxi.com/v1",
    "temperature": 0.4,
    "max_tokens": 4000
  }
}
```

然后设置环境变量：

```bash
export MINIMAX_API_KEY="你的key"
```

**方案 B：OpenAI**

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "api_key_env": "OPENAI_API_KEY",
    "base_url": null,
    "temperature": 0.4,
    "max_tokens": 4000
  }
}
```

```bash
export OPENAI_API_KEY="你的key"
```

### 3. 可选：配置搜索 API

如果需要额外的国际新闻覆盖，可以配置搜索 API：

```bash
export TAVILY_API_KEY="你的key"
export SERPER_API_KEY="你的key"
export FIRECRAWL_API_KEY="你的key"
```

---

## 使用

### 推荐运行时间

**北京时间 14:30**（土耳其时间 09:30，开盘前 30 分钟）

此时：
- BloombergHT 已发布当日突发新闻和重点新闻
- 前一天收盘总结已缓存（如有）
- 为开盘前提供最新市场动态

### 生成今日早报

```bash
python scripts/generate_briefing.py --config config.json
```

### 指定日期

```bash
python scripts/generate_briefing.py --force-date 2026-07-10 --config config.json
```

### 只生成 prompt（不调用 LLM）

```bash
python scripts/generate_briefing.py --force-date 2026-07-10 --config config.json --no-llm
```

---

## 输出

早报文件保存在：

```
output/{today_date}_daily_briefing_zh.txt          # 完整版
output/{today_date}_daily_briefing_brief_zh.txt    # 简报版
```

首次使用：`cp config.example.json config.json`，详见 `SETUP.md`。

---

## 数据来源

| 来源 | 内容 | 自动抓取 |
|------|------|---------|
| BloombergHT 收盘总结 | BIST 100、板块、汇率、黄金、原油 | ✅ |
| BloombergHT 突发新闻 | 伊朗、霍尔木兹、特朗普、OPEC | ✅ |
| BloombergHT 重点新闻 | JPMorgan、Morgan Stanley、大众裁员 | ✅ |
| Tavily/Serper/Firecrawl | 国际财经新闻 | 可选 |

---

## 常见问题

### Q: 报错 "Environment variable OPENAI_API_KEY is not set"

A: 设置环境变量即可：

```bash
export OPENAI_API_KEY="你的key"
# 或
export MINIMAX_API_KEY="你的key"
```

### Q: BloombergHT 文章抓取失败

A: 检查网络连接，确保能访问 `bloomberght.com`。

### Q: 早报内容太短或太长

A: 调整 `config.json` 中的 `llm.max_tokens`（默认 4000）。

### Q: 如何每天自动运行？

A: 使用 cron 或 Hermes Agent 的定时任务功能。

---

## 文件结构

```
turkey-morning-report-skill/
├── SKILL.md                    # 完整文档
├── QUICKSTART.md               # 本文件
├── config.json                 # 配置文件
├── scripts/
│   ├── generate_briefing.py    # 主入口
│   ├── fetch_bloomberght_closing.py  # BloombergHT 抓取
│   ├── fetch_news.py           # 新闻整合
│   ├── build_prompt.py         # Prompt 构建
│   ├── call_llm.py             # LLM 调用
│   ├── validate_output.py      # 输出验证
│   └── resolve_target_date.py  # 日期逻辑
├── templates/
│   └── morning_briefing_template.txt  # 参考模板
├── references/
│   ├── data_sources.md         # 数据源文档
│   ├── date_logic.md           # 日期逻辑文档
│   └── llm_provider_examples.md  # LLM 配置示例
└── example/
    ├── sample_output.txt       # 示例输出
    └── news_cache_sample.json  # 示例缓存
```

---

## 联系方式

有问题请提 GitHub Issue 或联系开发者。
