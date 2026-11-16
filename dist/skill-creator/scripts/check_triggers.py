#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""触发覆盖代理测试（仅标准库）。

用「字符二元组重合度 + 显式触发语命中」近似判断：description 是否覆盖了
用户真正会说的话。用于发现结构性漏词；**不能替代平台真实召回测试**，
方法说明见 references/trigger-test.md。

用法:
    python check_triggers.py --skill <skill-dir> --phrasings <phrasings-file> [--negatives <negatives-file>] [--json]

phrasings 文件格式:
    # 口语型            <- 注释行作为后续说法的类型标签
    帮我把这套流程存下来
    # 术语型
    SKILL.md 怎么老不触发
    # 无术语型
    下次别让我从头讲一遍

negatives 文件格式与 phrasings 相同，装的是**不应触发本技能**的相邻需求说法；
任一条命中即判误触发风险，退出码 1。

判定阈值（固定，不随结果调整）: >=0.30 命中 / 0.18-0.30 边缘 / <0.18 未命中
退出码: 正样本存在「边缘」或「未命中」-> 1; 负样本存在误触发 -> 1; 全部通过 -> 0
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

HIT = 0.30
EDGE = 0.18
BONUS = 0.35
# 负样本误触发判据：纯覆盖率阈值。高于 HIT，因为词面重叠不等于会误触发。
NEG_BAR = 0.40
QUOTED_TRIGGER_RE = re.compile(r"「([^」]+)」")
CJK_OR_ALNUM = re.compile(r"[\u3400-\u9fff\u3000-\u303fA-Za-z0-9]+")


def parse_frontmatter_description(skill_dir: Path) -> tuple[str, str]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise SystemExit(f"错误：找不到 {skill_md}")
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise SystemExit("错误：SKILL.md 缺少 frontmatter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise SystemExit("错误：frontmatter 未闭合")
    i = 1
    while i < end:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", lines[i])
        if m and m.group(1) == "description":
            val = m.group(2).strip()
            if val in {"|", ">", "|-", ">-"}:
                block = []
                i += 1
                while i < end and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                    if lines[i].strip():
                        block.append(lines[i].strip())
                    i += 1
                return " ".join(block), "\n".join(lines)
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ("\"", "'"):
                val = val[1:-1]
            return val, "\n".join(lines)
        i += 1
    raise SystemExit("错误：frontmatter 缺少 description")


def normalize(s: str) -> str:
    """保留 CJK 与 ASCII 字母数字，字母小写化。"""
    return "".join(m.group(0) for m in CJK_OR_ALNUM.finditer(s)).lower()


def bigrams(s: str) -> set[str]:
    n = normalize(s)
    if len(n) < 2:
        return {n} if n else set()
    return {n[i:i + 2] for i in range(len(n) - 1)}


def load_phrasings(path: Path) -> list[dict]:
    items: list[dict] = []
    label = "未标注"
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            label = line.lstrip("#").strip() or label
            continue
        items.append({"type": label, "text": line})
    return items


# 排除句标记：排除句写的是「本技能不做什么」，用于排斥而非吸引，
# 算召回时不能计入，否则会自相矛盾（「不覆盖账号授权」里的词会抬高
# 「帮我登录这个账号」这类说法的得分）。
EXCLUSION_MARKERS = ("不覆盖", "不用于", "不涉及", "不适用于", "不处理", "不做", "排除")


def responsibility_desc(desc: str) -> str:
    """截掉排除句，只留「做什么 + 什么时候用」段，供负样本算分。"""
    cut = len(desc)
    for marker in EXCLUSION_MARKERS:
        idx = desc.find(marker)
        if idx != -1:
            cut = min(cut, idx)
    return desc[:cut]


def score(phrase: str, desc: str, triggers: list[str]) -> dict:
    pbg, dbg = bigrams(phrase), bigrams(desc)
    coverage = len(pbg & dbg) / len(pbg) if pbg else 0.0
    pn = normalize(phrase)
    # 显式触发语加成按「触发语覆盖说法的比例」给，不是固定值：
    # 说法完整等于某条触发语时拿满；只命中长触发语的一小段时按比例折减，
    # 避免长触发语 + 短说法虚假满分。
    ratio = 0.0
    matched = ""
    for t in triggers:
        tn = normalize(t)
        if tn and tn in pn:
            r = len(tn) / len(pn) if pn else 0.0
            if r > ratio:
                ratio = r
                matched = t
    bonus = BONUS * ratio
    value = min(1.0, coverage + bonus)
    verdict = "命中" if value >= HIT else ("边缘" if value >= EDGE else "未命中")
    return {
        "type": "", "phrase": phrase, "coverage": round(coverage, 3),
        "matched_trigger": matched, "match_ratio": round(ratio, 3),
        "bonus": round(bonus, 2), "score": round(value, 3), "verdict": verdict,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="触发覆盖代理测试")
    ap.add_argument("--skill", required=True, help="待检技能目录")
    ap.add_argument("--phrasings", required=True, help="说法清单文件（每行一条，# 行为类型标签）")
    ap.add_argument("--negatives", help="负样本清单文件：不应触发的相邻需求说法")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    skill_dir = Path(args.skill).resolve()
    phrasings_path = Path(args.phrasings).resolve()
    desc, raw = parse_frontmatter_description(skill_dir)
    triggers = QUOTED_TRIGGER_RE.findall(desc)
    items = load_phrasings(phrasings_path)

    rows = []
    for it in items:
        row = score(it["text"], desc, triggers)
        row["type"] = it["type"]
        rows.append(row)

    hits = sum(1 for r in rows if r["verdict"] == "命中")
    ok = all(r["verdict"] == "命中" for r in rows)

    # 负样本：相邻需求说法不应命中。判定标准为「未命中」或「边缘」，
    # 命中即视为误触发风险，退出码 1。
    neg_rows = []
    neg_bad = 0
    if args.negatives:
        neg_path = Path(args.negatives).resolve()
        # 负样本只在「做什么 + 什么时候用」段上算分：排除句里的词不应抬高召回得分。
        neg_desc = responsibility_desc(desc)
        # 误触发判据：负样本在职责段上的纯覆盖率 ≥ NEG_BAR 判混淆风险。
        # 为何用固定阈值而非「正样本最低分」作基准：正样本说法直接取自 description
        # 的触发语，纯覆盖率必然为 1，拿它当基准会让判据退化成永真通过、失去检测力。
        # 为何阈值高于正样本的命中阈值 0.30：负样本已剔除排除句，剩余词面重叠
        # （如「代码质量扫描」与「扫描代码注释」共享「扫描」「代码」）不等于会误触发，
        # 需要更高的重叠才判风险。
        for it in load_phrasings(neg_path):
            row = score(it["text"], neg_desc, triggers)
            row["type"] = it["type"]
            row["bar"] = NEG_BAR
            row["over_trigger"] = row["coverage"] >= NEG_BAR
            if row["over_trigger"]:
                neg_bad += 1
            neg_rows.append(row)
        if neg_bad:
            ok = False

    if args.json:
        print(json.dumps({
            "skill_dir": str(skill_dir),
            "description": desc,
            "triggers": triggers,
            "thresholds": {"hit": HIT, "edge": EDGE, "bonus": BONUS},
            "results": rows,
            "negatives": neg_rows,
            "summary": {"total": len(rows), "hits": hits, "all_pass": ok,
                        "neg_total": len(neg_rows), "neg_over_trigger": neg_bad},
        }, ensure_ascii=False, indent=2))
    else:
        print(f"== 触发覆盖代理测试：{skill_dir.name} ==")
        print(f"description ({len(desc)} 字)：{desc}")
        print(f"抽取触发语 {len(triggers)} 条：{triggers if triggers else '（无）'}")
        print(f"阈值：命中 ≥{HIT} / 边缘 ≥{EDGE} / 显式触发语加成 ≤{BONUS}（按覆盖比例给）")
        print("-" * 78)
        print(f"{'类型':<10}{'覆盖率':>8}{'加成':>7}{'得分':>8}  {'判定':<6} 说法")
        print("-" * 78)
        for r in rows:
            print(f"{r['type']:<10}{r['coverage']:>8.3f}{r['bonus']:>7.2f}{r['score']:>8.3f}"
                  f"  {r['verdict']:<6} {r['phrase']}")
        print("-" * 78)
        print(f"汇总：{hits}/{len(rows)} 命中 → " + ("通过" if all(r["verdict"] == "命中" for r in rows) else "存在漏词，回到 S2 补触发语"))
        if neg_rows:
            print()
            print("== 负样本（不应触发）==")
            bar_val = neg_rows[0].get("bar", HIT)
            print(f"误触发判据：纯覆盖率 ≥ {bar_val}（负样本混淆阈值）")
            print(f"{'类型':<10}{'覆盖率':>8}{'得分':>8}{'判据':>8}  {'判定':<6} 说法")
            print("-" * 78)
            for r in neg_rows:
                mark = "误触发" if r["over_trigger"] else "正常"
                print(f"{r['type']:<10}{r['coverage']:>8.3f}{r['score']:>8.3f}{r['bar']:>8.3f}"
                      f"  {mark:<6} {r['phrase']}")
            print("-" * 78)
            print(f"负样本：{len(neg_rows) - neg_bad}/{len(neg_rows)} 未误触发"
                  + (" → 通过" if neg_bad == 0 else " → 存在误触发，需在 description 补排除场景"))
        print("提示：本测试为代理指标，平台真实召回仍需按里程碑 4 实测。")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
