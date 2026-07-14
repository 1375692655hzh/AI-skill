#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the LLM prompt for the close-of-day report."""
from __future__ import annotations

from pathlib import Path


def load_template(template_path: Path) -> str:
    return Path(template_path).read_text(encoding="utf-8")


def build_prompt(
    template_path: Path,
    today_date: str,
    target_date: str,
    weekday_cn: str,
    bloomberght_text: str,
    paraborsa_text: str,
    info_yatirim_text: str,
) -> str:
    template = load_template(template_path)

    system_instruction = """你是土耳其投资助理。请根据提供的当日收盘数据和券商研报，生成一份中文「土耳其股市收评」。

## 输出格式铁律（违反任何一条即为不合格）

1. 纯文本流式写作：只有【】作为章节标题，其余全部是连贯的段落文字。
2. 禁止一切分隔线：不许用 ━━━、===、--- 或任何线条分隔各章节。
3. 禁止表格：所有数据必须融入段落文字中叙述。
4. 禁止 Emoji：不许用 🔴🟢⚠️❌✅ 等任何表情符号。
5. 禁止列表符号：不许用 ①②③、•、*、-、数字编号等列表标记。多个要点之间用逗号或句号连接成自然段落。
6. 禁止 Markdown 加粗/斜体：正文不用 ** 或 __ 标记（标题中的【】除外）。
7. 禁止"第一/第二/第三"等结构化顺序词：核心信号与逻辑用自然段落展开，不要列条目。
8. 口吻：资深交易员收盘复盘，简洁、紧凑、有观点。
9. 篇幅：800-1500 字中文。
10. 换行规则：【】板块内部，如果讨论的是不同主题（如不同个股、不同板块、不同商品），每个主题之间用空行分隔，使结构更清晰。同一主题内的多句话保持连贯段落。

## 章节结构（按此顺序）

1. 【土耳其股市收评 — {today_date}（{weekday_cn}）】+ 核心结论段（今日收盘、关键驱动、明日展望）。
   - 必须严格以「核心结论：」开头，直接给出结论，不要任何铺垫。
2. 【大盘概况】（BIST 100收盘、振幅、日内关键点位、成交量、三日走势）。
3. 【关键个股异动】（成交量TOP5、涨跌榜、机构动向）。
4. 【行业板块表现】（领涨领跌板块、逻辑）。
5. 【汇市与大宗商品】（USD/TRY、EUR/TRY、黄金、原油、加密货币）。
6. 【核心信号与逻辑】（技术面、资金面、情绪面、分析师观点）。
7. 【后市策略参考】（仓位、支撑/阻力、方向、回避）。
8. 风险提示： + 一句话。

## 写作重点

- **收盘数据以 BloombergHT 的「Piyasalarda günün özeti」为核心来源；其他券商研报（Paraborsa、Info Yatırım）仅用于补充技术分析、支撑位/阻力位和观点，不得用来覆盖 BloombergHT 的当日收盘价、指数涨跌、成交量等核心数据。**
- 重点总结当日行情，参考券商研报中的技术分析和观点。
- 不包含国际新闻，除非直接影响土耳其市场（如油价因地缘变化）。
- 券商观点：Destek、Bizim、Bulls、İnfo、Integral 优先，不同券商观点冲突时择优采纳。
- 对不明来源或不可靠的数据，用" reportedly "或"市场分析认为"表述，不要编造具体数字。
"""

    prompt = template.format(
        today_date=today_date,
        target_date=target_date,
        weekday_cn=weekday_cn,
        bloomberght_text=bloomberght_text,
        paraborsa_text=paraborsa_text,
        info_yatirim_text=info_yatirim_text,
    )

    return system_instruction + "\n\n" + prompt


if __name__ == "__main__":
    import sys

    p = build_prompt(
        Path(sys.argv[1]),
        today_date="2026-07-10",
        target_date="2026-07-10",
        weekday_cn="周五",
        bloomberght_text="BIST 100 ...",
        paraborsa_text="Destek ...",
        info_yatirim_text="Info ...",
    )
    print(p)
