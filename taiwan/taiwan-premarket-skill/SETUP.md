# 部署指南 — 台股盘前早评 Skill

本 skill **自成一体**：复制本目录即可部署，不必安装盘后 skill。  
缺昨日库存时，入口脚本会在本目录内自动跑一遍 T-1 盘后数据层补齐。

成稿使用 OpenAI 兼容 LLM API（不再依赖本机 `claude -p`）。

---

## 1. 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.11+ |
| 网络 | TWSE / TAIFEX / 钜亨 cnyes；可选富途 OpenD |
| LLM | MiniMax / OpenAI 等 |

OpenD（可选增强）：

- 安装并启动富途 OpenD（默认 `127.0.0.1:11111`）
- 单独 venv 安装 `futu-api`
- 在 `config.json` → `opend.futu_python` 填该 python 路径

无 OpenD 时 ADR/费半层静默降级，仍可出稿（叙事靠 cnyes）。

---

## 2. 安装

```bash
cd taiwan-premarket-skill
pip install -r requirements.txt
cp config.example.json config.json
```

默认 `data_dir` / `output_dir` 都在本目录内。设置 API Key 后即可跑。

---

## 3. 运行

```bash
python scripts/generate_premarket_report.py --config config.json
python scripts/generate_premarket_report.py --config config.json --force-date 2026-07-15
python scripts/generate_premarket_report.py --config config.json --no-llm
python scripts/generate_premarket_report.py --config config.json --skip-collect
```

输出：

| 路径 | 说明 |
|------|------|
| `output/{date}/台股盘前早评_{date}.md` | 成稿 |
| `output/{date}/_数据简报_premarket.md` | 审计简报 |
| `data/{date}/premarket_digest.json` | 盘前数字汇总 |
| `data/{T-1}/...` | 自动补采的昨日库存（如原本没有） |

保底：

```bash
python run_fallback.py before 2026-07-15
```

---

## 4. 定时建议

台北时间交易日 **08:40** 左右。首次跑或隔了很久时，补采 T-1 会稍久（含 TWSE/TAIFEX）。

---

## 5. 文风

见 `STYLE.md`；范文见 `references/sample_premarket.md`、`example/sample_output.md`。
