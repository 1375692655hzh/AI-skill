# Quickstart

```bash
pip install -r requirements.txt
copy accounts.example.yaml accounts.yaml
copy .env.example .env
# 编辑 .env：填入下面两个 Key
```

## 要填的 API Key

| 环境变量 | 填什么 | 用途 |
|----------|--------|------|
| `XAI_API_KEY` | OpenRouter 的 `sk-or-v1-...`（[申请](https://openrouter.ai/keys)） | 抓取 X 帖（`x_search`） |
| `MINIMAX_API_KEY` | MiniMax Key | 翻译 + 精选报告 |

说明：变量名仍叫 `XAI_API_KEY`，但**默认填 OpenRouter Key**（与 `config.json` 里 `openrouter.ai` + `x-ai/grok-build-0.1` 配套）。不要填 kovar 的 sk-，也不要指望 chat/completions 路径。

```bash
# 先测抓取（不翻译、不精选）
python scripts/generate_x_influencer_report.py --config config.json --no-translate --no-curated
```

单次 x_search 约 10 条；脚本会按账号分页尽量抓全，仍受 `max_pages_per_account` / `per_account_limit` 限制。费用敏感时可设 `"tiers": ["core"]` 先只抓核心档。

完整流程：

```bash
python scripts/generate_x_influencer_report.py --config config.json --force-refresh
```

输出：

- `output/{date}_x_influencer_full_zh.txt`
- `output/{date}_x_influencer_curated_zh.txt`
