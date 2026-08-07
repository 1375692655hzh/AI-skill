# HK IPO skills

港股 / HKEX 新股相关 skill。**每个 skill 自成一体**：复制单个目录即可部署，默认数据写在本目录 `data/`，成稿在 `output/`。

| Skill | 说明 |
|-------|------|
| `hkipo-update-skill` | 港股新股每日刷新 + 6 时间点事件提醒（HKEX + Tiger + AAStocks 三源入 SQLite，命中事件才推 webhook） |

数据源：HKEX 披露易（金标准）+ Tiger JSON（结构化主源）+ AAStocks（交叉校验），全部免费免登录，在中国大陆可直连。

用法见 [hkipo-update-skill/QUICKSTART.md](hkipo-update-skill/QUICKSTART.md) 与 [hkipo-update-skill/SETUP.md](hkipo-update-skill/SETUP.md)。
