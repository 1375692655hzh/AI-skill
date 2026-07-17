# Quickstart

## 开箱即用（3 步）

```bash
pip install -r requirements.txt
# config.json 已附带，首次可复制：cp config.example.json config.json
$env:MINIMAX_API_KEY = "your-key"   # PowerShell
python scripts/generate_info_daily_report.py --config config.json
```

## 推荐执行时间（北京）

```
16:20 首发 → 16:30/40/50, 17:00/10 重试 → 20:00 兜底
```

`--no-llm` 只测抓取，不消耗 API。
