#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语域纪律过滤器 (规范 §4) —— 深度版与保底版共用。
禁用词扫描 + 散户表述->机构表述替换。"""
import re

# §4.2 禁用词 (含变体)
BANNED = ["绞肉机", "割韭菜", "挨打", "接盘", "跑路", "梭哈", "踩油门", "大佬",
          "鬼故事", "神救援", "神救", "說真話", "說假話", "韭菜", "庄家", "莊家",
          "拉爆", "腰斩", "腰斬", "起飞", "起飛", "梭一把", "抄底逃顶", "洗盤", "洗盘"]

# §4.3 替换规范 (繁简通吃; 长词在前避免部分匹配)
REPLACE = [
    ("神龍擺尾", "尾盘拉抬"), ("神救援", "尾盘承接"), ("大洗盤", "大幅震荡"),
    ("上沖下洗", "剧烈震荡"), ("上沖下洗", "剧烈震荡"), ("護盤", "承接力道"),
    ("殺跌", "卖压释放"), ("砸盤", "卖压释放"), ("重災區", "领跌族群"),
    ("跑路", "资金撤离"), ("散戶", "散户"), ("套牢", "持仓被套"),
    ("秒填息", "快速填息"), ("翻黑", "翻跌"), ("翻紅", "翻涨"),
]


def sanitize(text):
    """应用机构语域替换。返回过滤后文本。"""
    if not text:
        return text
    for a, b in REPLACE:
        text = text.replace(a, b)
    return text


def scan(text):
    """返回命中的禁用词列表 (空=合规)。"""
    return [w for w in BANNED if w in (text or "")]


if __name__ == "__main__":
    import sys
    t = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else ""
    hits = scan(t)
    print("禁用词命中:", hits if hits else "无 ✓")
