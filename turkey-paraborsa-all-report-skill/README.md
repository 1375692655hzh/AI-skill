# Turkey Paraborsa All-Broker Report Skill

Paraborsa **全量**券商评论抓取 + 中文综合报告（总结 + 拼接原文）。

## 开箱即用

```bash
cd turkey-paraborsa-all-report-skill
pip install -r requirements.txt
$env:MINIMAX_API_KEY = "your-key"
python scripts/generate_paraborsa_all_report.py --config config.json
```

## 报告结构

1. **【综合总结】**（LLM）：宏观共识、个股表格（标的/券商/看法）、券商速览、分歧点
2. **【拼接内容】**（机械拼接）：各券商土耳其语原文全文，按篇排列

## 推荐执行时间（北京）

```
22:00 首发 → 22:10/20/30 重试 → 23:00 兜底
```

## 测试（不调 LLM）

```bash
python scripts/generate_paraborsa_all_report.py --config config.json --force-date 2026-07-14 --no-llm
```

7/14 实测可发现约 **27 篇**（23 Borsa + 1 盘中 + 3 VİOP）。

## 文档

- `SKILL.md` — Agent 指令
- `SETUP.md` — 部署与 Cron
