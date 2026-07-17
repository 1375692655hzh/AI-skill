# 部署指南 — Turkey AA Morning Briefing Skill

抓取 Anadolu Agency 英文 Morning Briefing 全文，记录发布时间，NEWS IN BRIEF 置底。

---

## 开箱即用清单

| # | 项目 |
|---|------|
| 1 | 复制 `turkey-aa-morning-briefing-skill` 目录 |
| 2 | `pip install -r requirements.txt` |
| 3 | 运行 `generate_aa_morning_briefing.py` |

不需要 API Key，不需要其他项目。

---

## 安装

```bash
cd turkey-aa-morning-briefing-skill
pip install -r requirements.txt
# 首次可选
cp config.example.json config.json
```

Windows PowerShell：

```powershell
cd turkey-aa-morning-briefing-skill
pip install -r requirements.txt
Copy-Item config.example.json config.json
```

---

## 运行

```bash
# 抓取今日（土耳其日历；周末/假日默认回退到上一发布日）
python scripts/generate_aa_morning_briefing.py --config config.json

# 指定日期
python scripts/generate_aa_morning_briefing.py --config config.json --force-date 2026-07-16

# 指定原文 URL
python scripts/generate_aa_morning_briefing.py --config config.json --force-url "https://www.aa.com.tr/en/world/morning-briefing-july-16-2026/3999751"

# 忽略缓存重抓
python scripts/generate_aa_morning_briefing.py --config config.json --force-date 2026-07-16 --force-refresh
```

### 输出文件

| 路径 | 内容 |
|------|------|
| `output/{date}_aa_morning_briefing.txt` | 元数据 + 全文（NEWS IN BRIEF 在底部） |
| `.cache/turkey-aa-morning-briefing/aa_morning_briefing_{date}.json` | 抓取缓存 |

---

## 推荐 Cron（北京时间）

近 14 日实测：发布窗口约 TR 06:45–08:45（北京 11:45–13:45），**周末也常发**。建议：

```cron
10 12 * * *  cd /path/to/turkey-aa-morning-briefing-skill && python scripts/generate_aa_morning_briefing.py --config config.json
40 12 * * *  cd /path/to/turkey-aa-morning-briefing-skill && python scripts/generate_aa_morning_briefing.py --config config.json
10 13 * * *  cd /path/to/turkey-aa-morning-briefing-skill && python scripts/generate_aa_morning_briefing.py --config config.json
40 13 * * *  cd /path/to/turkey-aa-morning-briefing-skill && python scripts/generate_aa_morning_briefing.py --config config.json
10 14 * * *  cd /path/to/turkey-aa-morning-briefing-skill && python scripts/generate_aa_morning_briefing.py --config config.json
```

Windows 任务计划程序可按同样时间点调用上述命令。

---

## 配置说明

| 键 | 说明 |
|----|------|
| `target_date` | `auto` 或 `YYYY-MM-DD` |
| `skip_weekend` | 周末跳过（默认 false） |
| `skip_holidays` | 假日跳过（默认 true） |
| `sources.aa_morning_briefing.force_url` | 固定文章 URL（可空） |
| `holidays` | 跳过日期列表（ISO） |

---

## 校验

```bash
python scripts/validate_output.py output/2026-07-16_aa_morning_briefing.txt
```

必须看到 NEWS IN BRIEF 为最后一个已知板块。
