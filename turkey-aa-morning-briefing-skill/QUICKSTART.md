# Quickstart

```bash
pip install -r requirements.txt
python scripts/generate_aa_morning_briefing.py --config config.json --force-date 2026-07-16 --force-refresh
```

成功后查看：

```
output/2026-07-16_aa_morning_briefing.txt
```

确认文末是 `NEWS IN BRIEF`，以及文首有 `Published (TR UTC+3)` / `Published (Beijing UTC+8)`。
