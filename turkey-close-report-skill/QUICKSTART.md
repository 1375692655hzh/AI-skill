# 快速开始

## 一句话介绍

自动抓取土耳其当日收盘数据和券商研报，生成中文收评。收盘数据以 BloombergHT 为准，其他来源仅用于补充观点、技术位和市场情绪。

---

## 依赖安装

```bash
pip install requests beautifulsoup4 feedparser lxml
```

---

## 配置 LLM

编辑 `config.json`：

**MiniMax（推荐）**

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

说明：MiniMax-M3 默认输出 `\<think\>` 块，会污染纯文本收评格式。在需要结构化/纯文本输出时务必设置 `thinking: {type: "disabled"}`。

**OpenAI**

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "api_key_env": "OPENAI_API_KEY",
    "temperature": 0.4,
    "max_tokens": 8000
  }
}
```

---

## 设置环境变量

```bash
# MiniMax
export MINIMAX_API_KEY="你的key"

# 或 OpenAI
export OPENAI_API_KEY="你的key"
```

---

## 推荐运行时间

**北京时间 23:30+**（土耳其时间 18:30+，收盘后）

此时 BloombergHT 详细收盘已发布，券商评论完整。

---

## 使用

```bash
# 生成今日收评
python scripts/generate_close_report.py --config config.json

# 指定日期
python scripts/generate_close_report.py --force-date 2026-07-10 --config config.json

# 只生成 prompt（省钱 / 调试）
python scripts/generate_close_report.py --force-date 2026-07-10 --config config.json --no-llm
```

---

## 输出

文件保存到：

```
reports/hermes-briefings/{日期}_close_report_zh.txt
```

默认工作目录：`D:/AI项目/Turkey-investment`

---

## 数据源

| 源 | 时间 | 角色 | 内容 |
|---|------|------|------|
| BloombergHT 详细收盘 | TR ~18:30 | **核心** | BIST 100、板块、汇率、商品 |
| Paraborsa 券商评论 | TR ~16:30 | 辅助 | 券商观点、技术分析 |
| Info Yatırım 每日公告 | TR ~11:00 | 辅助 | 研报摘要 |
| Info Yatırım 技术分析 | TR ~12:00 | 辅助 | 支撑/阻力、技术信号 |

收盘数据以 BloombergHT 为准；Paraborsa 和 Info Yatırım 仅用于补充观点、技术位和市场情绪。

---

## 常见问题

**Q: 报错 "BloombergHT closing review not found"**
A: 可能还没收盘，建议 23:30 后再运行。

**Q: 明明指定了 13 日，报告里却出现 10 日数据**
A: 已加入日期校验。如果缓存内容与目标日期不匹配，会自动删除并重新抓取。若问题仍出现，请手动删除 `.cache/turkey-close-report/*_{date}.*` 后重试。

**Q: 报错缺少 API key**
A: 设置环境变量：`export MINIMAX_API_KEY="..."` 或 `export OPENAI_API_KEY="..."`

**Q: 输出不符合格式**
A: 检查 LLM 是否返回了 `**` 或列表符号。若使用 MiniMax-M3，请在 `config.json` 中设置 `thinking: {type: "disabled"}`。

---

## 更多文档

- `SKILL.md` — 完整文档
- `references/data_sources.md` — 数据源详情
- `example/sample_output.txt` — 示例输出
