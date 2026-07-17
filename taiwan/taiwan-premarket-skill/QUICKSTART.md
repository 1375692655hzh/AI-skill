# 快速开始 — 台股盘前

复制本目录即可，**不必**安装盘后 skill。缺昨日库存时会自动在本目录内补采。

```bash
cd taiwan-premarket-skill
pip install -r requirements.txt
cp config.example.json config.json
# 编辑 llm；设置 MINIMAX_API_KEY
python scripts/generate_premarket_report.py --config config.json
```

- 数据：`data/{日期}/`
- 成稿：`output/{日期}/台股盘前早评_*.md`

无 OpenD 也可跑（ADR/费半降级）。只出 prompt：加 `--no-llm`。
