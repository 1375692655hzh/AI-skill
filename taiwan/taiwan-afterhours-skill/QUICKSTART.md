# 快速开始 — 台股盘后

复制本目录即可，数据与成稿都在本目录内。

```bash
cd taiwan-afterhours-skill
pip install -r requirements.txt
cp config.example.json config.json
# 编辑 llm；设置 MINIMAX_API_KEY
python scripts/generate_afterhours_report.py --config config.json
```

- 数据：`data/{日期}/`
- 成稿：`output/{日期}/台股盘后内参_*.md`
