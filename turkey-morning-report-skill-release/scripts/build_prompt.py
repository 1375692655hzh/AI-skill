#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the LLM prompt from collected data and the template."""
from __future__ import annotations

from pathlib import Path


def load_template(template_path: Path) -> str:
    return Path(template_path).read_text(encoding="utf-8")


def build_prompt(
    template_path: Path,
    today_date: str,
    target_date: str,
    closing_text: str,
    news_text: str,
) -> str:
    template = load_template(template_path)

    system_instruction = """你是土耳其投资助理。请根据提供的前一交易日收盘回顾和新闻资讯，生成一份中文「土耳其股市早评」。

## 输出格式铁律（违反任何一条即为不合格）

1. 纯文本流式写作：只有【】作为章节标题，其余全部是连贯的段落文字。
2. 禁止一切分隔线：不许用 ━━━、===、--- 或任何线条分隔各章节。
3. 禁止表格：所有数据必须融入段落文字中叙述。
4. 禁止 Emoji：不许用 🔴🟢⚠️❌✅ 等任何表情符号。
5. 禁止列表符号：不许用 ①②③、•、*、-、数字编号等列表标记。多个要点之间用逗号或句号连接成自然段落。
6. 禁止 Markdown 加粗/斜体：正文不用 ** 或 __ 标记（标题中的【】除外）。
7. 口吻：资深交易员给朋友的简短分析，简洁、紧凑、有观点。
8. 篇幅：800-1200 字中文。
9. 换行规则：【】板块内部，如果讨论的是不同主题（如不同个股、不同板块、不同商品），每个主题之间用空行分隔，使结构更清晰。同一主题内的多句话保持连贯段落。

## 章节结构（按此顺序）

1. 【土耳其股市早评 — {today_date}】+ 核心观点段（昨日收盘、关键驱动、今日展望）。
   - 必须严格以「核心观点：」开头，直接给出结论，不要任何铺垫。
2. 【国际新闻】（2-3条新闻连写成段落，不编号）。
3. 【关键个股】（2-3只个股，每只一段话）。
4. 【行业板块表现】（领涨领跌 + 看点，一个完整段落）。
5. 【汇市与大宗商品】（所有品种融入一段文字叙述）。
6. 【今日操作参考】（仓位+点位+方向+回避，一两个段落）。
7. 风险提示：（一句话或半行，不单独成节）。

## 数据要求

- 标题日期用 **{today_date}**（今日）。
- 内容分析的是 **{target_date}**（前一交易日收盘）和之后至今日的资讯。
- 所有数字、涨跌幅、点位必须来自提供的素材，不编造。

## 参考模板风格

{template}
"""

    user_content = f"""### 前一交易日收盘回顾（{target_date}）

{closing_text}

### 期间新闻资讯

{news_text}

请严格按照上述格式铁律和章节结构生成中文早评。"""

    return system_instruction.format(
        today_date=today_date,
        target_date=target_date,
        template=template,
    ) + "\n\n" + user_content


if __name__ == "__main__":
    import sys

    tpl = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../templates/morning_briefing_template.txt")
    prompt = build_prompt(
        template_path=tpl,
        today_date="2026-07-13",
        target_date="2026-07-10",
        closing_text="（示例收盘数据）",
        news_text="（示例新闻数据）",
    )
    print(prompt)
