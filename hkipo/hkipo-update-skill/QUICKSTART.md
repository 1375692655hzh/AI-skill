# 快速开始 — 港股新股

复制本目录即可，SQLite 数据库与原始快照都在本目录内。

```powershell
cd hkipo-update-skill
pip install -r requirements.txt
Copy-Item config.example.json config.json
# 编辑 config.json：选 push.channel，设置对应 webhook 环境变量
python scripts/run_update.py --config config.json
python scripts/run_remind.py --config config.json --type offer_open
```

- 数据：`data/state.db`（SQLite 唯一持久层）+ `data/{日期}/`（原始快照，14 天清理）
- 成稿：`output/{日期}/daily_digest.md`
- 已上市归档：`data/archive/`（上市满 30 天移入，90 天后删除）

**6 个提醒时间点**（北京时间/HKT，由外部 Task Scheduler 触发）：
- 08:30 现金截止 / 09:00 招股开始+上市 / 13:30 融资截止 / 16:00 暗盘开始 / 17:00 资金解冻 / 18:15 暗盘结束

**没有事件 = 不推送。** 每个 slot 查库无命中 → 静默退出 0。
