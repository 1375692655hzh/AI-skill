# Turkey Close Report Skill

自动抓取土耳其当日收盘数据 + 券商研报 + 技术分析，生成中文收评。

---

## 功能

- **BloombergHT 详细收盘（核心数据源）**：BIST 100、板块、个股、汇率、黄金、原油
- **Paraborsa 券商评论（辅助观点）**：券商收盘观点、目标价、技术分析（Destek > Bizim > Bulls > İnfo > Integral）
- **Info Yatırım 每日公告（辅助研报）**：研报摘要、个股推荐
- **Info Yatırım 技术分析（辅助技术位）**：技术面分析、支撑/阻力位
- **日期校验**：抓取后自动校验内容日期是否与目标日期匹配；若缓存错位则自动丢弃并重新抓取
- **不包含国际新闻**：聚焦土耳其本土市场

注意：收盘数据（指数收盘价、涨跌幅、成交量、USD/TRY、EUR/TRY、黄金、原油）**必须以 BloombergHT 为准**，其他来源仅用于补充观点、技术位和市场情绪。

---

## 输出格式

```
【土耳其股市收评 — 2026年7月10日（周五）】

【核心结论】
...

【大盘概况】
...

【关键个股异动】
...

【行业板块表现】
...

【汇市与大宗商品】
...

【核心信号与逻辑】
...

【后市策略参考】
...

风险提示：...
```

---

## 推荐运行时间

**北京时间 23:30+**（土耳其时间 18:30+，收盘后）

此时：
- BloombergHT 详细收盘已发布
- Paraborsa 券商评论已发布
- 次日开盘前可直接参考

---

## 快速开始

### 1. 安装依赖

```bash
pip install requests beautifulsoup4 feedparser lxml
```

### 2. 配置 LLM

编辑 `config.json`，选择 LLM：

```json
{
  "llm": {
    "provider": "minimax",
    "model": "MiniMax-M3",
    "api_key_env": "MINIMAX_API_KEY",
    "base_url": "https://api.minimaxi.com/v1",
    "temperature": 0.4,
    "max_tokens": 8000,
    "thinking": { "type": "disabled" }
  }
}
```

说明：MiniMax-M3 默认输出 `<think>` 块，会污染纯文本收评格式。在需要结构化/纯文本输出时务必设置 `thinking: {type: "disabled"}`。

### 3. 设置环境变量

```bash
# MiniMax
export MINIMAX_API_KEY="你的key"

# 或 OpenAI
export OPENAI_API_KEY="你的key"
```

### 4. 生成收评

```bash
python scripts/generate_close_report.py --config config.json
```

---

## 命令

```bash
# 今日收评
python scripts/generate_close_report.py --config config.json

# 指定日期
python scripts/generate_close_report.py --force-date 2026-07-10 --config config.json

# 只生成 prompt
python scripts/generate_close_report.py --force-date 2026-07-10 --config config.json --no-llm
```

---

## 文件结构

```
turkey-close-report-skill/
├── SKILL.md                        # 完整文档
├── README.md                       # 本文件
├── QUICKSTART.md                   # 快速开始
├── config.json                     # 配置文件
├── scripts/
│   ├── generate_close_report.py    # 主入口（含日期校验）
│   ├── fetch_bloomberght.py        # BloombergHT 收盘抓取
│   ├── fetch_paraborsa.py          # Paraborsa 券商评论
│   ├── fetch_info_yatirim.py       # Info Yatırım 公告+技术分析（按日期归档页）
│   ├── check_source_date.py        # 内容日期校验
│   ├── build_prompt.py             # Prompt 构建
│   ├── call_llm.py                 # LLM 调用
│   ├── validate_output.py          # 输出验证
│   └── resolve_target_date.py      # 日期逻辑
├── templates/
│   └── close_report_template.txt   # 参考模板
├── references/
│   └── data_sources.md             # 数据源文档
└── example/
    └── sample_output.txt           # 示例输出
```

---

## 数据源

| 源 | 时间 | 角色 | 内容 |
|---|------|------|------|
| BloombergHT 详细收盘 | TR ~18:30 | **核心** | BIST 100、板块、个股、汇率、黄金、原油 |
| Paraborsa 券商评论 | TR ~16:30 | 辅助 | 券商观点、技术分析 |
| Info Yatırım 每日公告 | TR ~11:00 | 辅助 | 研报摘要 |
| Info Yatırım 技术分析 | TR ~12:00 | 辅助 | 支撑/阻力、技术信号 |

收盘数据以 BloombergHT 为准；Paraborsa 和 Info Yatırım 仅用于补充观点、技术位和市场情绪。

---

## 常见问题

**Q: 报错 "BloombergHT closing review not found"**
A: 可能是还没收盘或文章未发布，建议北京时间 23:30 后再运行。

**Q: 明明指定了 13 日，报告里却出现 10 日数据**
A: 已在 `generate_close_report.py` 中加入日期校验。如果缓存的内容与目标日期不匹配，会自动删除并重新抓取。若问题仍出现，请手动删除 `.cache/turkey-close-report/*_{date}.*` 后重试。

**Q: 没有券商评论数据**
A: Paraborsa 可能在节假日不发布，会 fallback 到 API 探测。

**Q: 输出太长或太短**
A: 调整 `config.json` 中的 `llm.max_tokens`。

---

## 许可证

MIT License
