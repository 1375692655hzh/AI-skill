# 部署指南 — Turkey X Influencer Report Skill

---

## 开箱即用清单

| # | 项目 |
|---|------|
| 1 | 复制 `turkey-x-influencer-report-skill` 目录 |
| 2 | `pip install -r requirements.txt` |
| 3 | 复制 `.env.example` → `.env`，填 **`XAI_API_KEY`**（OpenRouter 的 `sk-or-v1-...`） |
| 4 | `copy accounts.example.yaml accounts.yaml`（名单已对齐参考项目 31 个大V，可再改） |
| 5 | 在 `.env` 填 **`MINIMAX_API_KEY`**（翻译/精选） |
| 6 | 运行主脚本 |

不需要 Turkey-investment 主项目，也不需要 Twitter cookies。

---

## API Key 填什么

在 skill 目录创建 `.env`（可从 `.env.example` 复制）：

```env
# 抓取用 —— 填 OpenRouter Key（不是 console.x.ai，也不是 kovar）
XAI_API_KEY=sk-or-v1-xxxxxxxx
# 翻译/精选用
MINIMAX_API_KEY=xxxxxxxx
```

| 变量名 | 实际填入 | 申请地址 | 用途 |
|--------|----------|----------|------|
| `XAI_API_KEY` | OpenRouter `sk-or-v1-...` | https://openrouter.ai/keys | 调用 `x_search` 抓帖 |
| `MINIMAX_API_KEY` | MiniMax Key | MiniMax 控制台 | 中译 + 精选分析 |

配套默认配置（已在 `config.json`）：

- `xai_base_url`: `https://openrouter.ai/api/v1`
- `xai_model`: `x-ai/grok-build-0.1`
- `xai_api_mode`: `responses`（必须；chat/completions 不支持 `x_search`）

费用在 **OpenRouter** 账户扣。OpenRouter 需能访问该模型（含 xAI 的 `x_search`）。

也可兼容读取：`%USERPROFILE%\.hermes\x-influencer-market-monitor\.env`

也可把 `accounts_path` 指到本机 Hermes 名单：

```json
"accounts_path": "C:/Users/YOU/.hermes/x-influencer-market-monitor/accounts.yaml"
```

### 名单增删（给同事 / Agent）

- **加账号**：在 `accounts.yaml` 的 `accounts:` 下复制一块，改 `handle` / `name`，`enabled: true`
- **减账号**：删除该块，或 `enabled: false`
- **不必改 Python**；改完直接重跑 `generate_x_influencer_report.py`

---

## 抓取行为说明

| 项 | 行为 |
|----|------|
| 时间窗 | 土耳其时区 **昨天 00:00 → 当前时刻** |
| 单次上限 | x_search 约 **10 条/次** |
| 分页 | 按账号时间切段多次请求，尽量抓全 |
| 硬上限 | `max_pages_per_account`（默认 5）× `per_account_limit`（默认 50）；超限记 `truncated` |
| 费用 | ~31 账号 × 最多数页；可用 `tiers: ["core"]` 先只抓核心档 |

仍可能因 API/费用上限截断，报告 meta 会列出 `truncated_accounts`。

---

## 运行

```bash
cd turkey-x-influencer-report-skill
python scripts/generate_x_influencer_report.py --config config.json

# 忽略缓存重抓
python scripts/generate_x_influencer_report.py --config config.json --force-refresh

# 只出全文、不做精选
python scripts/generate_x_influencer_report.py --config config.json --no-curated

# 不翻译、不精选（测抓取）
python scripts/generate_x_influencer_report.py --config config.json --no-translate --no-curated
```

### 输出

| 路径 | 内容 |
|------|------|
| `output/{date}_x_influencer_full_zh.txt` | 原文 + 译文（含媒体链接） |
| `output/{date}_x_influencer_curated_zh.txt` | 精选分析 |
| `.cache/turkey-x-influencer-report/posts_{date}.json` | 缓存 |

---

## 推荐 Cron（北京时间，交易日）

BIST 开盘 TR 10:00 = 北京 15:00，建议开盘后半小时起抓：

```cron
30 15 * * 1-5  cd /path/to/turkey-x-influencer-report-skill && python scripts/generate_x_influencer_report.py --config config.json
50 15 * * 1-5  cd /path/to/turkey-x-influencer-report-skill && python scripts/generate_x_influencer_report.py --config config.json
10 16 * * 1-5  cd /path/to/turkey-x-influencer-report-skill && python scripts/generate_x_influencer_report.py --config config.json
```

脚本自身也会在周末/固定假日跳过。

---

## 配置说明

| 键 | 说明 |
|----|------|
| `fetch.provider` | 固定 `xai` |
| `fetch.window` | `yesterday_start_to_now`（TR 昨天 00:00→现在） |
| `fetch.timezone` | 默认 `Europe/Istanbul` |
| `fetch.xai_model` | 默认 `x-ai/grok-build-0.1`（OpenRouter） |
| `fetch.xai_base_url` | 默认 `https://openrouter.ai/api/v1` |
| `fetch.xai_api_mode` | 必须 `responses`（`x_search` 不支持 chat/completions） |
| `fetch.api_key_env` | 默认 `XAI_API_KEY`（OpenRouter 的 `sk-or-v1-...` 亦可） |
| `fetch.per_account_limit` | 每账号最多保留帖数（默认 50） |
| `fetch.max_pages_per_account` | 每账号最多分页次数（默认 5） |
| `fetch.account_delay_seconds` | 账号间隔（默认 1s） |
| `fetch.tiers` | 设为 `["core"]` 可只抓核心档，降低费用 |
| `fetch.min_priority` | 只抓不低于该优先级的账号 |
| `translate.enabled` | 是否翻译 |
| `curated.enabled` | 是否生成精选 |
| `holidays` | 额外休市日（固定假日已代码生成） |
