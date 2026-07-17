#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
保底方案编排器 —— 深度自动化被卡时的降级替代品。

依据: 深度版盘后须等16:00官方全量, 太晚; 钜亨〈台股盤後〉~14:20 即出。
      本程序纯 cnyes JSON API (无 JS/无 TWSE/无 OpenD), 快且稳, 差不多时点即抓,
      产出可直接发布的简要版, 保证「万一深度被卡还能发东西」。

模式:
  after (盘后保底, 建议 launchd 每交易日 ~14:30):  〈台股盤後〉+ 台幣 + 外資買賣超
  before(盘前保底, 建议 ~09:45, cnyes 无 08:40 前文, 取〈台股開盤〉):  开盘 wrap + 隔夜

纪律: 全篇 T3 二手, 显著标注「内容源:钜亨·二手同日」; 日期门禁(publishAt=目标日);
      语域过滤(lib/lexicon); 与官方口径差(如成交量)不对账, 属降级版可接受。

用法: python3 run_fallback.py [after|before] [YYYY-MM-DD]
"""
import sys, os, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collectors import cnyes
from lib import lexicon


def paragraphs(text, maxlen=1400):
    """清洗 wrap 正文, 按自然段落拆分, 返回段落列表 (供 \\n\\n 分隔渲染, 不再挤成一坨)。"""
    t = lexicon.sanitize(cnyes.clean(text))
    # cnyes 原文以换行分段; 先按换行拆, 再把过长段按句号切
    raw = [p.strip() for p in re.split(r"[\r\n]+", t) if p.strip()]
    paras, total = [], 0
    for p in raw:
        if total >= maxlen:
            break
        # 过长段落按句拆成 2 句一段, 便于阅读
        if len(p) > 200:
            sents = re.split(r"(?<=。)", p)
            buf = ""
            for s in sents:
                buf += s
                if len(buf) >= 110:
                    paras.append(buf.strip()); total += len(buf); buf = ""
            if buf.strip():
                paras.append(buf.strip()); total += len(buf)
        else:
            paras.append(p); total += len(p)
    return paras


def freshness_line(article):
    """可审计的抓取新鲜度标注: 文章发布台北时间 + 标题。"""
    pub = cnyes.taipei_date(article["publishAt"])
    hm = time.strftime("%H:%M", time.gmtime(article["publishAt"] + 8 * 3600))
    return f"发布 {pub} {hm}（台北）｜抓取 {time.strftime('%Y-%m-%d %H:%M')}"


def build_after(date, quo, stock):
    # 〈台股盤後〉分类会变(tw_quo/tw_stock 都可能), 合并两类搜, 避免踏空
    merged = (quo or []) + (stock or [])
    after = cnyes.pick(merged, date, ["〈台股盤後〉", "台股盤後", "盤後"])
    fx = cnyes.parse_fx(cnyes.pick(stock, date, ["台幣"]))
    foreign = cnyes.pick(stock, date, ["外資賣超", "外資買超", "外資"])
    if not after:
        return None, "当日〈台股盤後〉未发布 (未到~14:35 或休市)"
    md = [f"# 🚩 台股盘后简要（保底版）｜{date}", "",
          "> ⚠️ **保底降级版**，内容源＝钜亨（二手同日）。仅供深度官方版未及时产出时替代发布；数字以官方深度版为准，量能等口径或有差异。", "",
          f"> 🕒 {freshness_line(after)}", "",
          "## 📊 盘后综述", ""]
    md += _joined(paragraphs(after.get("content"), 1500))
    if fx and fx.get("close"):
        md += ["", "## 💱 汇率", "",
               f"新台币兑美元收 **{fx['close']}** 元，{fx.get('move') or '升贬详见来源'}。（台北外汇经纪／钜亨）"]
    if foreign:
        md += ["", "## 💰 外资动向", ""] + _joined(paragraphs(foreign.get("summary") or foreign.get("content"), 400))
    md += ["", "---", f"*🔖 来源：钜亨〈{lexicon.sanitize(after['title'])}〉等。保底版，非官方一手。*"]
    return "\n".join(md), None


def build_before(date, arts):
    # 优先〈台股盤前要聞〉(~05:10, 含隔夜/外资累计/台币/产业焦点); 退而求其次〈台股開盤〉(~09:40)
    pre = cnyes.pick(arts, date, ["盤前要聞"])
    kind = "盘前要闻"
    if not pre:
        pre = cnyes.pick(arts, date, ["〈台股開盤〉", "台股開盤", "開盤"])
        kind = "开盘速览"
    if not pre:
        return None, "当日〈台股盤前要聞〉/〈台股開盤〉均未发布 (未到~05:10 或休市)"
    note = ("此为清晨盘前要闻(隔夜美股/外资累计/台币/产业焦点)" if kind == "盘前要闻"
            else "cnyes 当日盘前要闻未及, 退用开盘后 wrap")
    md = [f"# 🚩 台股盘前简要（保底版）｜{date}", "",
          f"> ⚠️ **保底降级版**，内容源＝钜亨（二手同日）。{note}；供深度盘前版被卡时替代。", "",
          f"> 🕒 {freshness_line(pre)}", "",
          f"## 📈 {kind}", ""]
    md += _joined(paragraphs(pre.get("content"), 1600))
    md += ["", "---", f"*🔖 来源：钜亨〈{lexicon.sanitize(pre['title'])}〉。保底版。*"]
    return "\n".join(md), None


def _joined(paras):
    """段落列表 -> 每段独立成行、段间空行 (markdown 段落), 首字加 🔹 视觉锚。"""
    out = []
    for p in paras:
        out.append(f"🔹 {p}")
        out.append("")
    return out[:-1] if out else out


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "after"
    date = sys.argv[2] if len(sys.argv) > 2 else time.strftime("%Y-%m-%d")
    root = os.path.dirname(os.path.abspath(__file__))
    reports = os.environ.get("TAIWAN_EQUITY_REPORTS") or os.path.join(root, "output")
    outdir = os.path.join(reports, date)
    os.makedirs(outdir, exist_ok=True)

    if mode == "after":
        # 盘后维持原样 (单页, 〈台股盤後〉~14:20 wrap 在榜首)
        quo = cnyes.fetch_category("tw_quo", 30)
        stock = cnyes.fetch_category("tw_stock", 40)
        md, err = build_after(date, quo, stock)
        fname = f"保底_台股盘后简要_{date}.md"
    else:
        # 盘前: 盘前要闻(~05:10)午后会被埋, 多翻几页确保找到; 合并 tw_quo+tw_stock 搜
        quo = cnyes.fetch_recent("tw_quo", pages=2)
        stock = cnyes.fetch_recent("tw_stock", pages=6)
        md, err = build_before(date, quo + stock)
        fname = f"保底_台股盘前简要_{date}.md"

    if err:
        print(f"[保底-{mode}] {err}", file=sys.stderr)
        sys.exit(2)
    # 语域终检
    hits = lexicon.scan(md)
    if hits:
        print(f"[warn] 保底稿残留禁用词(已尽量替换): {hits}", file=sys.stderr)
    # freshness 审计: 目标日 == 系统当前台北日期? (防跨日误抓旧文)
    today = time.strftime("%Y-%m-%d")
    fresh_flag = "✅当日" if date == today else f"⚠️非当日(目标{date}≠今{today})"
    outp = os.path.join(outdir, fname)
    with open(outp, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[保底-{mode}] {fresh_flag} -> {outp}  ({len(md)}字符, 禁用词:{hits or '无'})")


if __name__ == "__main__":
    main()
