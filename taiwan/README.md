# Taiwan skills

台湾 / TWSE 相关 skill。**每个 skill 自成一体**：复制单个目录即可给同事部署，默认数据写在本目录 `data/`，成品在 `output/`。

| Skill | 说明 |
|-------|------|
| `taiwan-afterhours-skill` | 盘后内参（TWSE + TAIFEX → digest → LLM） |
| `taiwan-premarket-skill` | 盘前早评（自采 T-1 库存 + OpenD/cnyes → digest → LLM） |

互不依赖。盘前缺昨日库存时会在本 skill 内自动补采 T-1 盘后数据层，无需先装盘后 skill。

用法见各 skill 内 `QUICKSTART.md` / `SETUP.md`。
