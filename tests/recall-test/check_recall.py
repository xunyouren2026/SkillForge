#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""召回实测结果回归断言（仅标准库）。

作用：把 tests/recall-test/ 的真实召回实测结果固化为可重复运行的断言。
当 skill-creator 的 description 改动后，本脚本比对「当前 description 与实测时的
description 是否一致」：不一致就提醒重跑实测，避免实测结论与代码脱节。

用法:
    python tests/recall-test/check_recall.py [--skill <技能目录>] [--decisions <decisions.json>]

退出码: 0 通过 / 1 断言失败或 description 已变更需重跑 / 2 环境错误
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SKILL = ROOT / "dist" / "skill-creator"
DEFAULT_DECISIONS = Path(__file__).resolve().parent / "decisions.json"
# 实测时的 description 指纹。改动 description 后须重跑召回实测并更新此值。
EXPECTED_DESC_SHA = "f590a9cd"


def desc_of(skill_dir: Path) -> str:
    main = skill_dir / "SKILL.md"
    if not main.is_file():
        return ""
    for line in main.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip()
    return ""


def fingerprint(text: str) -> str:
    """description 指纹：前 8 位 sha256。"""
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def main():
    ap = argparse.ArgumentParser(description="召回实测结果回归断言")
    ap.add_argument("--skill", default=str(DEFAULT_SKILL), help="被测技能目录")
    ap.add_argument("--decisions", default=str(DEFAULT_DECISIONS), help="实测判定记录")
    args = ap.parse_args()

    skill_dir = Path(args.skill).resolve()
    decisions_path = Path(args.decisions).resolve()
    if not skill_dir.is_dir():
        sys.stderr.write("技能目录不存在：%s\n" % skill_dir)
        return 2
    if not decisions_path.is_file():
        sys.stderr.write("判定记录不存在：%s\n" % decisions_path)
        return 2

    desc = desc_of(skill_dir)
    if not desc:
        sys.stderr.write("未能从 SKILL.md 读出 description\n")
        return 2

    print("== 召回实测回归断言 ==")
    print("技能包：%s" % skill_dir.name)

    # 1. description 指纹一致性
    fp = fingerprint(desc)
    print("description 指纹：%s（实测时 %s）" % (fp, EXPECTED_DESC_SHA))
    desc_changed = fp != EXPECTED_DESC_SHA
    if desc_changed:
        print("[FAIL] description 已变更：实测结论不再适用于当前 description，"
              "须重跑召回实测并更新 EXPECTED_DESC_SHA 与 decisions.json")
        print("判定：不通过")
        return 1
    print("[PASS] description 未变更，实测结论仍适用")

    # 2. 判定记录自身的一致性：三次判断一致，且与 should_trigger 一致
    entries = json.loads(decisions_path.read_text(encoding="utf-8"))
    problems = []
    for e in entries:
        q = e.get("query", "")
        should = e.get("should_trigger")
        ds = e.get("decisions", [])
        if not ds:
            problems.append("%s：无判定记录" % q)
            continue
        if len(set(ds)) != 1:
            problems.append("%s：三次判断不一致 %s（判断抖动）" % (q, ds))
            continue
        got = ds[0] == "skill-creator"
        if got != should:
            problems.append("%s：判定为 %s，期望 %s" % (q, ds[0], should))
    if problems:
        for p in problems:
            print("[FAIL] %s" % p)
        print("判定：不通过")
        return 1

    pos = sum(1 for e in entries if e["should_trigger"])
    neg = len(entries) - pos
    total_judgments = sum(len(e["decisions"]) for e in entries)
    print("[PASS] %d 条 query 判定自洽：正样本 %d 条、负样本 %d 条，共 %d 次独立判断无抖动"
          % (len(entries), pos, neg, total_judgments))
    print("判定：通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
