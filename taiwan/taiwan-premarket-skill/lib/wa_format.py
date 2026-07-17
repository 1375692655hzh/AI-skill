#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告 markdown -> WhatsApp 纯文本格式。
WhatsApp 语法: *粗体* _斜体_ ~删除线~ ```等宽```; 不认 ## 标题/** 粗体/| 表格/> 引用。

规则:
- 删除「🔢 数字—来源台账」整段(用户要求不发)
- 标题 #/##/### -> 去井号, 用 *粗体* (emoji 保留)
- **粗体** -> *粗体*  ; 行内保留 emoji
- 表格行/分隔线 -> 去掉(WhatsApp 不渲染表格)
- > 引用、--- 分隔线 -> 去掉或换空行
- 多余空行压缩

用法: python3 lib/wa_format.py <报告.md>  -> stdout 纯文本
      import: to_whatsapp(md_text) -> str
"""
import sys, re


def to_whatsapp(md, drop_ledger=True):
    lines = md.split("\n")
    out = []
    skip = False
    for ln in lines:
        s = ln.rstrip()

        # 台账段开始 -> 之后全部丢弃 (台账通常是全文最后一段)
        if drop_ledger and re.search(r"(数字\s*[—\-–]\s*来源台账|数字—来源台账|来源台账)", s):
            skip = True
            continue
        if skip:
            continue

        # 表格分隔行 |---|---| 丢弃
        if re.match(r"^\s*\|?[\s:\-|]+\|[\s:\-|]*$", s) and "-" in s:
            continue
        # 表格数据行 | a | b | -> "a: b"
        if s.count("|") >= 2 and s.strip().startswith("|"):
            cells = [c.strip() for c in s.strip().strip("|").split("|")]
            cells = [c for c in cells if c]
            if cells:
                out.append("・" + " ｜ ".join(cells))
            continue

        # 水平分隔线 --- / *** -> 空行
        if re.match(r"^\s*([-*_]\s*){3,}$", s):
            out.append("")
            continue

        # 标题 #/##/### -> *内容* (保留行首 emoji)
        m = re.match(r"^\s*#{1,6}\s*(.+)$", s)
        if m:
            title = _inline(m.group(1)).strip()
            # 去掉已有的 * 再包一层, 避免 **
            title = title.strip("*")
            out.append(f"*{title}*")
            continue

        # 引用 > xxx -> 去掉标记
        s = re.sub(r"^\s*>\s?", "", s)

        out.append(_inline(s))

    # 压缩连续空行为最多1个
    txt = "\n".join(out)
    txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
    return txt


def _inline(s):
    """行内: **x**->*x*, 去掉残留 markdown 记号。"""
    # **粗体** 或 __粗体__ -> *粗体*
    s = re.sub(r"\*\*(.+?)\*\*", r"*\1*", s)
    s = re.sub(r"__(.+?)__", r"*\1*", s)
    # 列表 - / * 开头 -> ・
    s = re.sub(r"^\s*[-*]\s+", "・", s)
    # 行内 `code` -> 去反引号
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s


if __name__ == "__main__":
    md = open(sys.argv[1], encoding="utf-8").read()
    print(to_whatsapp(md))
