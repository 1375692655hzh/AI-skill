#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate AA Morning Briefing output text."""
from __future__ import annotations

import re
from typing import List, Tuple


KNOWN_SECTIONS = [
    "TOP STORIES",
    "BUSINESS & ECONOMY",
    "SPORTS",
    "NEWS IN BRIEF",
]


def validate_output(text: str) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not text or not text.strip():
        return False, ["empty output"]

    if "Source:" not in text:
        errors.append("missing Source metadata line")

    # Split header / body
    body = text
    if "=" * 20 in text:
        body = text.split("=" * 20, 1)[-1]

    # Find section header positions (line-start)
    positions: dict[str, int] = {}
    for m in re.finditer(r"(?m)^(TOP STORIES|BUSINESS & ECONOMY|SPORTS|NEWS IN BRIEF)\s*$", body):
        name = m.group(1)
        if name not in positions:
            positions[name] = m.start()

    if "NEWS IN BRIEF" not in positions:
        # Soft warning: some days might omit it — still flag
        errors.append("NEWS IN BRIEF section not found")
    else:
        nib_pos = positions["NEWS IN BRIEF"]
        for name, pos in positions.items():
            if name == "NEWS IN BRIEF":
                continue
            if pos > nib_pos:
                errors.append(f"NEWS IN BRIEF not at bottom: {name} appears after it")

        # NEWS IN BRIEF should be the last known section
        last_known = max(positions.values())
        if nib_pos != last_known:
            errors.append("NEWS IN BRIEF must be the last known section (bottom)")

    if "TOP STORIES" not in positions:
        errors.append("TOP STORIES section not found")

    # Hard fail only for bottom ordering / emptiness
    hard = [
        e
        for e in errors
        if "empty" in e or "bottom" in e or "appears after" in e
    ]
    return (len(hard) == 0), errors


if __name__ == "__main__":
    import sys
    from pathlib import Path

    p = Path(sys.argv[1])
    ok, errs = validate_output(p.read_text(encoding="utf-8"))
    print("OK" if ok else "FAIL")
    for e in errs:
        print("-", e)
