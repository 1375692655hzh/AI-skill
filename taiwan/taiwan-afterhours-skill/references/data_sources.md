# 数据源（盘后）

| 数据 | 源 | 备注 |
|------|-----|------|
| 指数/宽度/个股 | TWSE rwd MI_INDEX | 禁用 openapi v1 |
| 三大法人 | TWSE BFI82U | 官方口径 |
| 个股法人 | TWSE T86 | ~16:00–16:30 发布，脚本会等待 |
| 量能 | TWSE FMTQIK | |
| 期货外资未平仓 | TAIFEX futContractsDate | HTML 解析 |
| 汇率 | cnyes〈台幣〉 | 二手同日 |

纪律：日期门禁、收盘/法人闭环、缺数静默降级。
