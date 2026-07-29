# -*- coding: utf-8 -*-
"""Generate two close-report variants for source ablation (2026-07-27).

A: BloombergHT only
B: BloombergHT + Info technical bulletin (tech levels only)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_prompt import build_prompt
from call_llm import call_llm
from generate_close_report import format_bloomberght, WEEKDAYS_CN
from llm_runner import generate_with_validation
from runtime_utils import configure_stdio
from validate_output import validate

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "turkey-close-report"
OUT = ROOT / "output"
TARGET = date(2026, 7, 27)


def load_minimax_key() -> str:
    env = os.environ.get("MINIMAX_API_KEY")
    if env:
        return env
    hermes = Path(
        r"C:/Users/hzh/AppData/Local/hermes/profiles/turkey-stock/"
        r"skills/research/turkey-close-report-skill/config.json"
    )
    if hermes.is_file():
        key = json.loads(hermes.read_text(encoding="utf-8"))["llm"]["api_key"]
        os.environ["MINIMAX_API_KEY"] = key
        return key
    raise RuntimeError("MINIMAX_API_KEY not found")


def load_bht_with_news() -> dict:
    """Load BHT close wrapper (text + breaking/featured news)."""
    close_wrap = CACHE / f"bloomberght_close_{TARGET.isoformat()}.json"
    if close_wrap.is_file():
        wrap = json.loads(close_wrap.read_text(encoding="utf-8"))
        if wrap.get("closing_review"):
            return wrap
    closing = CACHE / f"bloomberght_closing_{TARGET.isoformat()}.json"
    if closing.is_file():
        raw = json.loads(closing.read_text(encoding="utf-8"))
        return {
            "ok": raw.get("ok", True),
            "closing_review": {"text": raw.get("text", "")},
            "breaking_news": [],
            "featured_news": [],
        }
    raise FileNotFoundError("BHT cache missing")


def load_tech_only() -> str:
    info = json.loads((CACHE / f"info_yatirim_{TARGET.isoformat()}.json").read_text(encoding="utf-8"))
    tech = (info.get("technical") or {}).get("content") or ""
    if not tech.strip():
        raise RuntimeError("Info technical content empty")
    # Strip tutorial fluff about how to read RSI if possible — keep levels
    lines = []
    skip_markers = (
        "RSI Nasıl",
        "MACD Nasıl",
        "Stochastic",
        "CCI Nasıl",
        "Çekince:",
        "Mersis",
        "UNSUBSCRIBE",
        "www.",
        "@",
        "Barbaros Mah",
    )
    for line in tech.splitlines():
        if any(m in line for m in skip_markers):
            continue
        if line.strip().startswith("İnfo Yatırım"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines).strip()
    header = (
        "【技术位参考 — 仅供【核心信号与逻辑】【后市策略参考】中的支撑/阻力/均线表述使用；"
        "不得覆盖收盘价、涨跌幅、板块、个股成交与汇市大宗数字；"
        "不得编造 RSI/MACD 的当日具体读数（素材若无数值则不要写具体数值）。】\n"
    )
    return header + cleaned


EXTRA_RULES_A = """
## 本次素材约束（必须遵守）
- 唯一事实来源是「核心收盘数据」（当日 BloombergHT 收盘综述及盘中/重点资讯标题）。
- 没有券商评论、没有技术简报。技术支撑阻力若素材未给出，用「关注整数关口/前低」等弱表述，禁止编造 RSI/MACD 具体数值与均线拐头断言。
- 个股只能基于素材中的成交额/涨跌幅名单写事实；禁止编造个股涨跌原因（除非资讯标题直接相关）。
"""

EXTRA_RULES_B = """
## 本次素材约束（必须遵守）
- 收盘价、涨跌幅、高低点、成交额个股、涨跌幅个股、板块、汇市与大宗商品：只能来自「核心收盘数据」。
- 「技术与公告参考」里只有技术简报摘录：仅可用于【核心信号与逻辑】和【后市策略参考】中的支撑/阻力/60日均线/Bollinger 等技术位表述。
- 禁止用技术简报覆盖收盘数字；禁止编造 RSI/MACD 当日具体读数（简报若只有指标用法说明、没有当日数值，就不要写具体 RSI/MACD 数字）。
- 禁止引入券商观点；禁止把「上周五」数据写成今日。
"""


def build_variant_prompt(label: str, bht: dict, tech_text: str, extra_rules: str) -> str:
    template = ROOT / "templates" / "close_report_template.txt"
    weekday = WEEKDAYS_CN[TARGET.weekday()]
    prompt = build_prompt(
        template_path=template,
        today_date=TARGET.isoformat(),
        target_date=TARGET.isoformat(),
        weekday_cn=weekday,
        bloomberght_text=format_bloomberght(bht),
        paraborsa_text="",  # unused
        info_yatirim_text=tech_text if tech_text else "",
    )
    # build_prompt still has empty sections; inject rules before final instruction
    prompt = prompt.replace(
        "请生成完整中文收评。成品不得出现任何机构、平台、网站、报告名称。",
        extra_rules.strip()
        + f"\n\n【实验标签：{label}】\n请生成完整中文收评。成品不得出现任何机构、平台、网站、报告名称。",
    )
    return prompt


def run_one(label: str, prompt: str, llm_cfg: dict, out_name: str) -> Path:
    prompt_file = CACHE / f"close_prompt_{TARGET.isoformat()}_{label}.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    print(f"[{label}] prompt -> {prompt_file}")

    content, result = generate_with_validation(prompt, llm_cfg, validate, fix_attribution=True)
    out = OUT / out_name
    if content is None:
        raise RuntimeError(f"{label} LLM failed: {result}")
    if not result.get("ok"):
        raw = CACHE / f"close_raw_{TARGET.isoformat()}_{label}.txt"
        raw.write_text(content, encoding="utf-8")
        print(f"[{label}] validation failed: {result.get('errors')}; raw -> {raw}")
        # still save for comparison if content exists
        out.write_text(content, encoding="utf-8")
        print(f"[{label}] wrote unvalidated draft -> {out}")
        return out

    if result.get("warnings"):
        print(f"[{label}] warnings: {result['warnings']}")
    out.write_text(content, encoding="utf-8")
    print(f"[{label}] OK -> {out} ({len(content)} chars)")
    return out


def main() -> None:
    configure_stdio()
    load_minimax_key()
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    llm_cfg = cfg["llm"]

    bht = load_bht_with_news()
    print("BHT closing text len:", len((bht.get("closing_review") or {}).get("text") or ""))
    print("breaking:", len(bht.get("breaking_news") or []), "featured:", len(bht.get("featured_news") or []))

    tech = load_tech_only()
    print("Tech excerpt len:", len(tech))

    OUT.mkdir(parents=True, exist_ok=True)

    prompt_a = build_variant_prompt("A_BHT_ONLY", bht, "", EXTRA_RULES_A)
    prompt_a = prompt_a.replace(
        "### 技术与公告参考\n\n（无技术/公告数据）",
        "### 技术与公告参考\n\n（本次实验不提供技术/公告数据）",
    )
    prompt_a = prompt_a.replace(
        "### 市场观点与情绪\n\n（无市场观点数据）",
        "### 市场观点与情绪\n\n（本次实验不提供券商观点）",
    )

    prompt_b = build_variant_prompt("B_BHT_PLUS_TECH", bht, tech, EXTRA_RULES_B)
    prompt_b = prompt_b.replace(
        "### 市场观点与情绪\n\n（无市场观点数据）",
        "### 市场观点与情绪\n\n（本次实验不提供券商观点）",
    )

    run_one(
        "A",
        prompt_a,
        llm_cfg,
        f"{TARGET.isoformat()}_close_report_A_bht_only_zh.md",
    )
    run_one(
        "B",
        prompt_b,
        llm_cfg,
        f"{TARGET.isoformat()}_close_report_B_bht_tech_zh.md",
    )
    print("DONE")


if __name__ == "__main__":
    main()
