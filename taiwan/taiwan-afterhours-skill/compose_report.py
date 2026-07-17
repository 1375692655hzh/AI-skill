#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成稿层：把数据层(digest + 原始)组装成「数据简报」，喂给 claude -p 依规范成稿。
把「数据准备(确定性Python)」与「写作(claude -p)」解耦——数字只来自简报，claude 不取数不编造。

用法:
  python3 generate.py afterhours 2026-07-08
  python3 generate.py premarket  2026-07-09
输出: reports/YYYY-MM-DD/台股{盘后内参|盘前合刊}_YYYY-MM-DD.md
"""
import sys, os, json, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

from lib.roots import code_root, data_dir as resolve_data_dir

ROOT = code_root(__file__, up=1)
DATA = resolve_data_dir(ROOT)
# Optional override for report output parent (set by generate_*.py)
REPORTS = os.environ.get("TAIWAN_EQUITY_REPORTS") or os.path.join(ROOT, "output")


def _num(x):
    s = re.sub(r"[,]|<[^>]+>", "", str(x))
    try:
        return float(s)
    except ValueError:
        return None


def load(d, name):
    p = os.path.join(DATA, d, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


# ---------- 盘后数据简报 ----------
def brief_afterhours(date):
    L = []
    dg = load(date, "digest.json") or {}
    L.append(f"# 盘后数据简报 {date}（全部已过日期门禁；闭环校验：{[c for c in dg.get('checks',[])]}）")
    # 大盘
    if dg.get("ohlc"):
        o = dg["ohlc"]; L.append(f"\n## 大盘\nOHLC 开{o['open']} 高{o['high']} 低{o['low']} 收{o['close']}")
    if dg.get("ma"):
        m = dg["ma"]
        L.append(f"## 均线(截至当日): 收{m['close']} MA5={m.get('ma5')} MA10={m.get('ma10')} "
                 f"MA20={m.get('ma20')} 距20日线{m.get('vs_ma20_pct')}% | 状态: {m.get('ma20_state')}")
    for t in dg.get("taiex", []):
        L.append(f"  {t['date']} 收{t['close']} 涨跌{t['chg']} 量{t['amount_e8']}亿")
    # 报酬指数 + 除权息
    ind = load(date, "twse_stock_all.json")
    if ind:
        for t in ind.get("tables", []):
            for r in t.get("data", []):
                if "報酬" in str(r[0]) and "加權" in str(r[0]):
                    L.append(f"含息报酬指数 {r[1]} 涨跌点{r[3]} ({r[4]}%)")
        # 除权息家数
        for t in ind.get("tables", []):
            fs = [str(x) for x in (t.get("fields") or [])]
            if any("證券代號" in x for x in fs) and any("收盤價" in x for x in fs):
                ex = [f"{r[0].strip()}{r[1].strip()}" for r in t["data"] if len(r) > 9 and "X" in str(r[9])]
                L.append(f"今日除权息 {len(ex)} 档: {', '.join(ex[:12])}")
                px = {r[0].strip(): (r[1].strip(), _num(r[8]), str(r[9]), _num(r[10])) for r in t["data"] if len(r) >= 11}
                break
    # 宽度
    if dg.get("breadth"):
        b = dg["breadth"]
        L.append(f"\n## 宽度(股票口径) 上涨{b.get('上漲(漲停)',{}).get('stock')} 下跌{b.get('下跌(跌停)',{}).get('stock')} 持平{b.get('持平',{}).get('stock')}")
    # 类股
    mi = load(date, "twse_mi_index_ind.json")
    if mi:
        L.append("\n## 类股指数(收/涨跌%)")
        want = ["發行量加權", "未含金融", "未含電子", "半導體", "電子零組件", "電腦", "光電", "通信網路",
                "其他電子", "金融保險", "塑膠類", "塑膠化工", "航運", "水泥類", "電機機械", "油電燃氣",
                "生技醫療", "觀光", "貿易百貨", "鋼鐵", "汽車"]
        for r in mi["tables"][0]["data"]:
            if any(w in r[0] for w in want):
                L.append(f"  {r[0].strip()} 收{r[1]} {r[3]}({r[4]}%)")
    # 法人 + 期货 + 连续
    L.append("\n## 资金")
    L.append(f"三大法人(亿): {dg.get('inst_net_e8')}")
    if dg.get("foreign_streak"):
        s = dg["foreign_streak"]; L.append(f"外资连续{s['direction']}{s['days']}日 累计{s['cum_e8']}亿")
    if dg.get("taifex"):
        L.append(f"外资台指期净部位: {dg['taifex']}")
    if dg.get("fx"):
        L.append(f"新台币: 收{dg['fx'].get('close')} {dg['fx'].get('move')}")
    # 法人连续买卖超个股 (inst_streak)
    try:
        from lib import inst_streak
        res = inst_streak.compute(date, window=10, cache_dir=DATA)
        if res:
            L.append("\n## 法人连续买卖超个股(近{}交易日, 张)".format(res["window"]))
            for who, wl in [("foreign", "外资"), ("trust", "投信")]:
                for direction in ["买超", "卖超"]:
                    rows = inst_streak.top_list(res, who, direction, 4, 6)
                    if rows:
                        L.append(f"{wl}连续{direction}: " + "; ".join(
                            f"{c}{nm}(连{dd}{'+' if cap else ''}日,今{td/1000:+.0f})" for c, nm, dd, td, cum, cap in rows))
            cf = inst_streak.crossfire(res)[:8]
            if cf:
                L.append("土洋对做: " + "; ".join(f"{nm}(外资{fd}连{fdd}/投信{td}连{tdd})" for c, nm, fd, fdd, td, tdd, _ in cf))
    except Exception as e:
        L.append(f"(inst_streak 失败: {e})")
    # T86 当日买卖超前列 + 个股价格
    if dg.get("t86_foreign_buy"):
        L.append("\n## 当日T86买卖超前列(张)")
        L.append("外资买超: " + "; ".join(f"{x['code']}{x['name']}+{x['foreign_lot']}" for x in dg["t86_foreign_buy"][:8]))
        L.append("外资卖超: " + "; ".join(f"{x['code']}{x['name']}{x['foreign_lot']}" for x in dg["t86_foreign_sell"][:8]))
        L.append("投信买超: " + "; ".join(f"{x['code']}{x['name']}+{x['trust_lot']}" for x in dg["t86_trust_buy"][:6]))
    return "\n".join(L)


# ---------- 盘前数据简报 ----------
def brief_premarket(date):
    dg = load(date, "premarket_digest.json") or {}
    L = [f"# 盘前数据简报 {date}（昨日库存={dg.get('prev_trading_day')}）"]
    L.append(f"\n## 台北昨收: {dg.get('taipei_prev_close')}")
    if dg.get("prev_afterhours"):
        L.append(f"## 前一日盘后库存: {json.dumps(dg['prev_afterhours'], ensure_ascii=False)}")
    if dg.get("us_indices_cnyes"):
        L.append(f"## 隔夜美股四大点位(cnyes二手): {json.dumps(dg['us_indices_cnyes'], ensure_ascii=False)}")
    if dg.get("us_indices_proxy"):
        parts = [f"{n} {v['chg_pct']:+}%(代理{v['proxy']})" for n, v in dg["us_indices_proxy"].items()]
        L.append(f"## 隔夜美股四大涨跌(OpenD ETF代理,仅涨跌幅准/非点位): {', '.join(parts)}")
    if dg.get("opend", {}).get("quotes"):
        L.append("## 隔夜ADR/费半成分(OpenD一手):")
        for c, q in dg["opend"]["quotes"].items():
            L.append(f"  {c} last={q['last']} chg={q['chg_pct']}%")
        if dg["opend"].get("adr_premium"):
            L.append(f"## ADR溢价折价: {json.dumps(dg['opend']['adr_premium'], ensure_ascii=False)}")
    if dg.get("ma"):
        m = dg["ma"]
        L.append(f"## 昨日均线(供20日线分析): 收{m['close']} MA5={m.get('ma5')} MA10={m.get('ma10')} "
                 f"MA20={m.get('ma20')} 距20日线{m.get('vs_ma20_pct')}% | 状态: {m.get('ma20_state')}")
    if dg.get("margin_t1"):
        mt = dg["margin_t1"]
        fin_chg = (mt['融资金额今日_仟元'] - mt['融资金额前日_仟元']) / 1e6 if mt.get('融资金额今日_仟元') and mt.get('融资金额前日_仟元') else None
        sec_chg = (mt['融券今日_单位'] - mt['融券前日_单位']) if mt.get('融券今日_单位') and mt.get('融券前日_单位') else None
        L.append(f"## 融资融券T-1({mt['date']}): 融资余额今{round(mt['融资金额今日_仟元']/1e6,1) if mt.get('融资金额今日_仟元') else '—'}亿"
                 f"(较前日{'+' if (fin_chg or 0)>=0 else ''}{round(fin_chg,1) if fin_chg is not None else '—'}亿), "
                 f"融券余额今{mt.get('融券今日_单位')}单位(较前日{'+' if (sec_chg or 0)>=0 else ''}{sec_chg if sec_chg is not None else '—'})")
    if dg.get("fx"):
        L.append(f"## 新台币: {dg['fx']}")
    if dg.get("cnyes_premarket"):
        L.append(f"\n## 钜亨盘前要闻(叙事源, publishAt={dg['cnyes_premarket']['publishAt']}):\n{dg['cnyes_premarket']['content'][:1800]}")
    if dg.get("night_futures"):
        nt = dg["night_futures"]
        dc = nt.get("day_close")
        anchor = ""
        if dc and nt.get("close") is not None:
            diff = nt["close"] - dc
            anchor = f" | 夜盘vs日盘收{dc}: {'+' if diff>=0 else ''}{diff:.0f} 隐含开盘{'偏多' if diff>0 else '偏空' if diff<0 else '平'}"
        L.append(f"## 台指期夜盘(开盘锚,官方一手): 开{nt.get('open')} 高{nt.get('high')} 低{nt.get('low')} 收{nt.get('close')} 涨跌{nt.get('chg')}{anchor}")
    if dg.get("calendar", {}).get("exright_by_day"):
        L.append("\n## 股市行事历-未来除权息日程(官方一手):")
        for day, items in sorted(dg["calendar"]["exright_by_day"].items()):
            L.append(f"  {day}: {len(items)}档 {', '.join(items[:10])}")
    if dg.get("handoff"):
        L.append(f"\n## 前一日盘后交接的盘前部署(隔夜锚须用上方最新数据刷新):\n{dg['handoff']}")
    if dg.get("degraded"):
        L.append(f"\n## 降级项(静默降级,不出现在正文,只在台账注明): {dg['degraded']}")
    return "\n".join(L)


# ---------- 规范/纪律 prompt ----------
DISCIPLINE = """\
【铁律】① 数字只能用「数据简报」里的，禁止自行取数或编造任何数字；简报没有的字段静默省略或降为定性，禁占位。
② 全文机构投研语汇，冷峻客观、事实先行；禁用词(绞肉机/割韭菜/护盘/杀跌/神救援/腰斩/起飞/庄家/韭菜等)一律不用，散户口语换机构表述；用词：观测点(不「侦测双阈值」)/低吸(不「低接」)/道指(不「道琼」)/影响(不「具体传导」)/关键位(不「关键位网格」)/台股期指(夜盘统一叫法,不「开盘锚/夜盘期指」)；**避免军事化战斗用词**(「攻击目标」→「定价目标」)；**个股名去 `*` 号**(国巨*→国巨)；章节标题不带内部标签(「纯事实/机制层/≤N字」)、也不带括号副标(「市场表现与传导（隔夜锚）」去掉括号注)。
③ 结论前置；核心判断附可证伪阈值；揭示性偏好(法人实际买卖/期指部位/汇率)证据等级高于口头。
④ 章节加 emoji 标注(🚩结论 📊大盘 💰资金 💱汇率 🏭行业 🎯个股 🔢台账 等)；段落之间留白，勿挤成一坨。
⑤ 文末必附「🔢 数字—来源台账」：逐类数字标来源(官方一手/二手同日/派生)+性质；闭环校验只在台账里列(正文不提校验)；降级项列出。
⑥ 只输出 markdown 正文，不要任何前言/说明/解释。"""

PROMPT_AFTERHOURS = """你是台股机构投研分析师，据下方【数据简报】撰写《台股盘后内参》(当日交易日 {date})。

结构(四层金字塔，顺序不可调换，全文2500-3800字)。**章节名不带「一、二、三、四」序号**(用 `📊 大盘`、`💰 资金` 而非 `📊 一、大盘`)。

**文风(最重要，本质是做减法，不是加口语点评)**：
- 保持机构投研的冷峻客观，事实与判断先行。**不要**为了「点评感」加「真金白银在减仓」「独木难支」「性价比偏低」「不是口头看淡而是…」这类口语化、戏剧化的评述——这是过火，不要。
- **删冗余与学术黑话**：不写「证据链清晰」「结构主导」「当前最高证据等级」「揭示性证据(坐实)」「证据一致/证据充分」「闭环校验通过」「分项和=合计」这类自证/学术/自我总结措辞；**事实列够即止，不补「所以证据一致」这类总结句**；「期货部位(揭示性证据)」直接写「股指期货」。校验只在台账，正文不提。
- **没信息增量的内容直接删**，连「XX持平/无方向性意义/此处从略」这类说明句都不写。
- **避免军事化/战斗用词**(「攻击目标」→「定价目标」)；**个股名去 `*` 号**(国巨*→国巨、国建*→国建)；删冗余词(「评价有支撑」→「有支撑」)。
- 长句适度拆成短自然段，一句一个意思；判断给到位即可，不铺陈、不堆形容词。

以加粗「🚩 核心研判」开篇(可分2-3个短自然段：方向定性→资金面→关键位与操作姿态；简洁，勿长句堆叠、勿口语点评)。

📊 **大盘**：点位/涨跌/量能/盘中开高低收，**均线与箱体并入走势描述、不单列重复段**(据简报「均线」：收盘相对MA20位置(距%)+型态ma20_state+结合MA5/MA10判中期方向，融入首段，不要写「均线未提供」)；市场宽度(涨跌家数)；除权息旺季计入除息蒸发+含息报酬指数对照。段末加一句加粗「📊 **大盘综评**：…」。

💰 **资金**(法人/期货/汇率)：三大法人(合计→外资/投信/自营分项+外资连续天数)；期货段标题用「**股指期货**」(不写「期货部位(揭示性证据)」)；**法人连续买卖超个股(近10日)**——外资连买/外资连卖/投信连买**三行各在句末结论前加一个 emoji 强化**(如 🟢买超集中于…/🔴卖压集中于…/🔵投信偏…)；土洋对做；汇率(收盘+升贬,与外资流向是否同向)。**融资融券完全不提**(静默省略，不写任何说明句，不入台账降级)。段末加一句加粗「💰 **资金与筹码综评**：…」。

🏭 **行业**：官方类股提炼领涨领跌——**领涨行前加 🔴、领跌行前加 🟢**(台股红涨绿跌)；**变动小的板块(约±0.5%内的持平类)直接不写、连「XX持平/无方向性意义」这类说明句都不要**(没信息增量就删掉,不占行)；挑代表方向、类似板块合并,不逐一罗列全表；高低切定性(未含电子vs未含金融印证)。段末加一句加粗「🏭 **行业综评**：…」。

🎯 **个股异动**：权值背离+异动股,一股一句结论+驱动因素(法人买卖/营收催化/除息填息)。**法说/营收日程若简报无则静默不提**(不写「日程未提供/不予虚列」)。段末加一句加粗「🎯 **个股综评**：…」。

**不含「次日展望/盘前部署」**(该内容归次日盘前)。
🔢 数字—来源台账。

{discipline}

【数据简报】
{brief}"""

PROMPT_PREMARKET = """你是台股机构投研分析师，据下方【数据简报】撰写《台股盘前早评》(交易日 {date}，开盘前发布)。标题首行输出 `# 台股盘前早评（{date}）`。

结构(7个模块，顺序：🚩核心结论→📈市场表现与传导→⚙️关键驱动→🖥️交易台观点→📊昨日速览→🎯盘前策略→🔭观测与情景，无「板块A/B」分隔，约2600-3400字)。**盘前定位=今日作战部署，正餐在「隔夜+夜盘+今日部署」；昨日只做T-1速览并指向盘后，不重复盘后已详述的大盘/筹码复盘。**

以加粗「🚩 核心结论」开篇(≤180字：方向定性→隔夜性质→关键位→操作姿态；**最后一句加粗操作姿态**)。

## 📈 市场表现与传导
盘前正餐之一(盘后没有)。含：
- **隔夜行情**：美股四大指数——**直接写指数名+涨跌(用「道指/标普500/纳指」，不写「ETF代理」字样，实现细节留台账)**，有 cnyes 点位则带点位，皆无才静默(**正文不写「未提供/降级不列」，缺项只在台账栏**)。费半直接写「费半(SOXX)+X%」(**不写「代理」**)，**点明「内部分化」还是「全面齐杀」**+成分个股(领跌/龙头)；台系ADR(TSM/UMC/ASX)；**台指期夜盘(用简报「台指期夜盘」)**；油金(背离则分析)；新台币(昨夜收盘锚)。**长句用句号拆短、勿用破折号拉长句。**
- **对台股今日的影响**：分点(台积电/半导体设备记忆体链/封测等)落到台股**具体个股**的开盘影响，**不做机械板块1:1映射、宁缺勿凑**。
- **台积电ADR隐含方向**：据简报ADR溢价写隐含台币价/升水%/相对涨停参考价；异常宽幅升水**一句点明成因(结构性长期溢价/费半强势/汇率垫高)即可，不写「不构成硬边界/不宜机械解读为必攻涨停」这类免责套话，也不写「见下」等自我指涉**；附联电/日月光ADR隐含方向。
- **台股期指(开盘方向)**：**据简报「台指期夜盘」写**，夜盘统一称「**台股期指**」(不写「开盘锚」「夜盘期指」这类术语)，直接起句如「台股期指夜盘收X、较昨现货收盘+Y点，指向开盘偏多」；再结合ADR+费半佐证。

## ⚙️ 关键驱动
盘前正餐之二。机制层，其一/其二/其三，每个驱动此处展开一次(如外资提款+汇率双螺旋、费半性质变化、记忆体涨价vs评价杀)，解析对利率/新台币/外资流向/评价的实质影响。

## 🖥️ 交易台观点
约180字，**可拆成2段(资金本质一段、操作含义一段)**：①隔夜资金行为本质②对台股今日开盘是拉抬还是抽离+操作含义。禁复述前文数字/机制。可适度口语化机构表述，但不堆戏剧化词。

## 📊 昨日速览
**压缩、可分「大盘」「筹码」两小段**：上一交易日收盘/涨跌/量能定性、关键位、均线MA20位置(据简报「昨日均线」一句带过)；另起一段写筹码要点(法人+外资连卖天数+期指净空+融资券T-1+涨跌家数)。**盘后已详述故此处不展开、不逐项分析；但不要写「详细拆解见昨日盘后内参」这类指引句**。日期非紧邻前一日写实际日期不写「昨日」。

## 🎯 盘前策略
盘前正餐之三。**内容上延续昨日防御/进攻基调并以隔夜数据校准，但正文直接写结论(如「策略维持昨日防御风格」)，禁「承接T-1基准/承接盘后交接/以隔夜数据刷新」这类流程说明句**：战术姿态(仓位上限)；分层应对(守某位/破某位做什么)；关键位(标题就叫「关键位」不叫「关键位网格」，列上方压力/下方支撑点位)；回避清单；日程风险(据简报「行事历-除权息」列今日及次日重点档数标的)。

## 🔭 观测与情景
观测点(外资现货卖超收敛/扩大的量级阈值、台指期外资净空转增或转减)；两分支情景预案(多方/空方，各附触发确认条件)。

---
## 🔢 数字—来源台账
**分层列示**：官方一手(TWSE/TAIFEX法人期货宽度/夜盘)／二手同日(digest的指数点位/新台币/个股昨收)／二手同日(钜亨盘前要闻叙事的提款金额/法说数字)／一手(OpenD ADR与费半成分/SOXX/油金)／派生(ADR隐含价与溢价、涨跌停参考价，带换算式)／降级缺项(不占位，不含融资融券)。**闭环校验**只在台账列关键式。**口径差**并列标注、不合并。

{discipline}

【数据简报】
{brief}"""


def call_llm_compose(prompt, llm_cfg=None):
    """Call OpenAI-compatible API. llm_cfg from config.json['llm']."""
    from call_llm import call_llm
    cfg = llm_cfg or {}
    BACKOFFS = [30, 60, 120]
    last_err = None
    for attempt in range(len(BACKOFFS) + 1):
        try:
            md = call_llm(
                prompt=prompt,
                provider=cfg.get("provider", "minimax"),
                model=cfg.get("model", "MiniMax-M3"),
                api_key_env=cfg.get("api_key_env", "MINIMAX_API_KEY"),
                base_url=cfg.get("base_url"),
                temperature=float(cfg.get("temperature", 0.4)),
                max_tokens=int(cfg.get("max_tokens", 8000)),
                timeout=int(cfg.get("timeout", 300)),
            ).strip()
            if md.startswith("```"):
                md = md.split("\n", 1)[1] if "\n" in md else md
                if md.endswith("```"):
                    md = md.rsplit("\n", 1)[0]
            if md:
                return md.strip()
        except Exception as e:
            last_err = e
            print(f"[compose] attempt {attempt+1} failed: {e}", file=sys.stderr)
        if attempt < len(BACKOFFS):
            time.sleep(BACKOFFS[attempt])
    print(f"[compose] LLM 失败: {last_err}", file=sys.stderr)
    return None


def postprocess(md):
    """机械后处理: 强制执行 claude 常犯的几条固定规则(纯机械, 不改语义)。"""
    # 1. 章节标题去括号副标: '## 📈 市场表现与传导（隔夜锚）' -> 去括号
    md = re.sub(r'^(#{1,4}\s*[^\n（(]*?)[（(][^）)\n]*[）)]\s*$', r'\1', md, flags=re.M)
    # 2. 个股名去 * 号: 「国巨*」「国建*」-> 删单个*(前为中文/数字, 非 markdown ** 的一部分)
    md = re.sub(r'(?<=[一-龥0-9])(?<!\*)\*(?!\*)', '', md)
    return md


def compose(mode, date, llm_cfg=None, no_llm=False):
    global DATA, REPORTS
    DATA = resolve_data_dir(ROOT)
    REPORTS = os.environ.get("TAIWAN_EQUITY_REPORTS") or os.path.join(ROOT, "output")

    if mode == "afterhours":
        brief = brief_afterhours(date)
        prompt = PROMPT_AFTERHOURS.format(date=date, discipline=DISCIPLINE, brief=brief)
        fname = f"台股盘后内参_{date}.md"
    elif mode == "premarket":
        brief = brief_premarket(date)
        prompt = PROMPT_PREMARKET.format(date=date, discipline=DISCIPLINE, brief=brief)
        fname = f"台股盘前早评_{date}.md"
    else:
        raise ValueError("mode 必须是 afterhours 或 premarket")

    outdir = os.path.join(REPORTS, date)
    os.makedirs(outdir, exist_ok=True)
    brief_path = os.path.join(outdir, f"_数据简报_{mode}.md")
    open(brief_path, "w", encoding="utf-8").write(brief)
    prompt_path = os.path.join(outdir, f"_prompt_{mode}.txt")
    open(prompt_path, "w", encoding="utf-8").write(prompt)
    print(f"[compose] 简报 {len(brief)}字 -> {brief_path}", file=sys.stderr)

    if no_llm:
        print(f"[compose] --no-llm: prompt -> {prompt_path}", file=sys.stderr)
        return prompt_path

    print(f"[compose] 调 LLM 成稿({mode}) ...", file=sys.stderr)
    md = call_llm_compose(prompt, llm_cfg)
    if not md:
        print("[compose] LLM 成稿失败(重试耗尽)", file=sys.stderr)
        sys.exit(3)
    md = postprocess(md)
    try:
        from lib import lexicon
        hits = lexicon.scan(md)
        if hits:
            print(f"[compose] ⚠️ 禁用词残留: {hits}", file=sys.stderr)
    except Exception:
        pass
    outp = os.path.join(outdir, fname)
    open(outp, "w", encoding="utf-8").write(md)
    print(f"✅ 成稿 -> {outp} ({len(md)}字)")
    return outp


def main():
    mode = sys.argv[1]
    date = sys.argv[2] if len(sys.argv) > 2 else time.strftime("%Y-%m-%d")
    no_llm = "--no-llm" in sys.argv
    compose(mode, date, no_llm=no_llm)


if __name__ == "__main__":
    main()
