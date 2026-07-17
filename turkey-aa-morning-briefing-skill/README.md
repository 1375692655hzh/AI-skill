# Turkey AA Morning Briefing Skill

每日抓取 [AA English Morning Briefing](https://www.aa.com.tr/en/world/morning-briefing-july-16-2026/3999751) 全文，记录发布/更新时间，并将 **NEWS IN BRIEF** 固定排到文末。

## 开箱即用

```bash
cd turkey-aa-morning-briefing-skill
pip install -r requirements.txt
python scripts/generate_aa_morning_briefing.py --config config.json
```

不需要 LLM，不需要 Turkey-investment 主项目。把整个目录打包给同事即可。

## 推荐执行时间（北京）

近 14 日实测发布窗口约 **TR 06:45–08:45**（北京 **11:45–13:45**），周末也常有稿。

```
12:10 首发 → 12:40 / 13:10 / 13:40 重试 → 14:10 兜底（含周末）
```

## 测试指定日期

```bash
python scripts/generate_aa_morning_briefing.py --config config.json --force-date 2026-07-16 --force-refresh
```

输出：`output/2026-07-16_aa_morning_briefing.txt`

## 文档

- `SKILL.md` — Agent 指令
- `SETUP.md` — 部署与 Cron
- `QUICKSTART.md` — 最短上手
