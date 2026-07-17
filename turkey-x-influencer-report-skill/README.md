# Turkey X Influencer Report Skill

开盘后经 **OpenRouter → xAI `x_search`** 抓取名单内 X 大V 帖子（土耳其时区 **昨天 00:00 → 现在**），输出：

1. **全文**：原文 + 中文译文（含媒体链接）  
2. **精选**：LLM 筛选投资热点 + 背景 + 投资分析（偏土耳其/BIST）

## 开箱即用

```bash
cd turkey-x-influencer-report-skill
pip install -r requirements.txt
copy accounts.example.yaml accounts.yaml
copy .env.example .env
# 编辑 .env：
#   XAI_API_KEY=sk-or-v1-...   ← OpenRouter（https://openrouter.ai/keys）
#   MINIMAX_API_KEY=...        ← 翻译/精选
python scripts/generate_x_influencer_report.py --config config.json
```

无需 twitter-cli / Twitter cookies。详见 `QUICKSTART.md` / `SETUP.md`。

## 推荐执行时间（北京）

```
15:30 首发 → 15:50 / 16:10 重试（交易日；周末假日跳过）
```

## 文档

- `SKILL.md` — Agent 指令  
- `SETUP.md` — 部署与 Cron  
- `QUICKSTART.md` — 最短上手  
