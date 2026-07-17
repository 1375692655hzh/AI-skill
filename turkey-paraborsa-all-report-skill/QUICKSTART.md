# Quickstart

```bash
pip install -r requirements.txt
$env:MINIMAX_API_KEY = "your-key"
python scripts/generate_paraborsa_all_report.py --config config.json --force-date 2026-07-14 --no-llm
```

`--no-llm` 只测全量抓取和拼接，约 1–3 分钟。
