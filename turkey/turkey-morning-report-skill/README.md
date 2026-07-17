# 🇹🇷 Turkey Morning Report Skill

自动抓取土耳其市场数据 + 国际财经新闻，生成中文早报。

---

## 功能

- **BloombergHT 三源抓取**：收盘总结 + 突发新闻 (SON DAKİKA) + 重点新闻 (Öne Çıkan Haberler)
- **国际财经覆盖**：地缘政治、OPEC、美联储、央行、科技股、大宗商品
- **智能 LLM 生成**：资深交易员风格，纯文本格式，800-1200 字
- **多 API 支持**：MiniMax、OpenAI、智谱等 OpenAI 兼容 API
- **搜索 API 可选**：Tavily、Serper、Firecrawl 作为新闻补充

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

或手动安装：

```bash
pip install requests beautifulsoup4 feedparser
```

### 2. 配置 LLM API

编辑 `config.json`，选择一个 LLM 提供商：

**MiniMax（推荐国内用户）**
```json
{
  "llm": {
    "provider": "minimax",
    "model": "MiniMax-M3",
    "api_key_env": "MINIMAX_API_KEY",
    "base_url": "https://api.minimaxi.com/v1"
  }
}
```

**OpenAI**
```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "api_key_env": "OPENAI_API_KEY"
  }
}
```

### 3. 设置环境变量

```bash
# 选择一个
export MINIMAX_API_KEY="你的key"
# 或
export OPENAI_API_KEY="你的key"
```

### 4. 生成早报

```bash
python scripts/generate_briefing.py --config config.json
```

成品在 `output/` 目录：

| 文件 | 说明 |
|------|------|
| `{日期}_daily_briefing_zh.txt` | 完整早评（800–1200 字） |
| `{日期}_daily_briefing_brief_zh.txt` | 结构化简报（汉字+中文标点 200–520 字，个股每只一行） |

简报版示例格式：

```
【土耳其股市早报简报 — 2026-07-15】
指数：BIST 100 14080点（-0.09%），14000关口拉锯
汇率：美元/里拉47.03，黄金大涨2.3%
驱动：美联储鹰派 + 地缘升温
个股：ASELS 高换手 | THYAO 成交居首
板块：金属/保险领涨，科技领跌
操作：五成以下防御，关注14115/13940
风险：地缘冲突、油价波动
```

关闭简报：在 `config.json` 设 `"brief": {"enabled": false}`。

---

## 命令

```bash
# 生成今日早报
python scripts/generate_briefing.py --config config.json

# 指定日期
python scripts/generate_briefing.py --force-date 2026-07-10 --config config.json

# 只生成 prompt（不调用 LLM）
python scripts/generate_briefing.py --force-date 2026-07-10 --config config.json --no-llm
```

---

## 数据来源

| 来源 | 内容 | 自动抓取 |
|------|------|---------|
| BloombergHT 收盘总结 | BIST 100、板块、汇率、黄金、原油、加密货币 | ✅ |
| BloombergHT 突发新闻 | 伊朗、霍尔木兹、特朗普、OPEC、美联储 | ✅ |
| BloombergHT 重点新闻 | JPMorgan、Morgan Stanley、大众裁员、经济数据 | ✅ |
| Tavily/Serper/Firecrawl | 国际财经新闻补充 | 可选 |

---

## 输出格式

纯文本，无 markdown、无 emoji、无表格、无列表：

```
【土耳其股市早评 — 2026-07-10】

核心观点：昨日BIST 100收涨1.41%报14304.36点...

【国际新闻】
特朗普强硬表态称美国将"夺取霍尔木兹海峡控制权"...

【关键个股】
ASELS昨日成交额突破200亿里拉稳居市场第一...

THYAO成交约154亿里拉排名第二...

【行业板块表现】
领涨板块集中在旅游、金属制品机械...

【汇市与大宗商品】
美元里拉收报46.98较前一日微涨0.16%...

【今日操作参考】
建议战术性收紧至五成仓位以下...

风险提示：中东局势升级可能引发全球避险情绪急剧升温。
```

---

## 配置说明

| 配置项 | 说明 |
|--------|------|
| `output_dir` | 输出目录，默认 `output` |
| `cache_dir` | 缓存目录，默认 `.cache/turkey-morning-report` |
| `workdir` | 工作目录，默认 `.`（skill 目录本身） |
| `sources.news.bloomberght.enabled` | 启用 BloombergHT 新闻抓取 |
| `sources.news.mode` | `agent`（调用者提供新闻）或 `api`（skill 自动搜索） |
| `sources.news.search_engine` | 搜索 API 配置（Tavily/Serper/Firecrawl） |
| `llm` | LLM 提供商配置 |
| `holidays` | 土耳其假期列表（跳过生成） |

---

## 文件结构

```
turkey-morning-report-skill/
├── SKILL.md                        # 完整文档
├── README.md                       # 本文件
├── QUICKSTART.md                   # 快速开始
├── SETUP.md                        # 部署指南（给同事）
├── config.example.json             # 配置模板
├── requirements.txt                # Python 依赖
├── scripts/
│   ├── generate_briefing.py        # 主入口
│   ├── fetch_bloomberght_closing.py # BloombergHT 抓取
│   ├── fetch_news.py               # 新闻整合
│   ├── build_prompt.py             # Prompt 构建
│   ├── call_llm.py                 # LLM 调用
│   ├── validate_output.py          # 输出验证
│   ├── resolve_target_date.py      # 日期逻辑
│   └── search_api.py               # 搜索 API
├── templates/
│   └── morning_briefing_template.txt
├── references/
│   ├── data_sources.md             # 数据源文档
│   ├── date_logic.md               # 日期逻辑文档
│   └── llm_provider_examples.md    # LLM 配置示例
└── example/
    ├── sample_output.txt           # 示例输出
    └── news_cache_sample.json      # 示例缓存
```

---

## 常见问题

**Q: 报错 "Environment variable OPENAI_API_KEY is not set"**
设置环境变量：`export OPENAI_API_KEY="你的key"`

**Q: BloombergHT 文章抓取失败**
检查网络连接，确保能访问 `bloomberght.com`

**Q: 早报内容太短或太长**
调整 `config.json` 中的 `llm.max_tokens`（默认 4000）

**Q: 如何每天自动运行？**
使用 cron 或 Hermes Agent 的定时任务功能

---

## 许可证

MIT License

---

## 联系方式

有问题请提 GitHub Issue 或联系开发者。
