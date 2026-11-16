#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能健康度体检（A3）自动化实现（仅标准库，Python 3.8+）。

把 A3 手册（references/health-check.md 第 9.3 节）的七步执行流程固化为脚本：
结构校验 → 描述合规 → 触发面测试 → 产出抽样 → 引用新鲜度 → 生成报告 → 判定处置。

用法:
    python scripts/health_check.py <skill-dir> [--report <输出路径>] [--json]
        [--phrasings <说法文件>] [--negatives <负样本文件>] [--samples <产出目录>]

产出:
    Markdown 体检报告，默认写 <skill-dir>/../tests/health_<日期>.md（包外）；
    --json 时只打印 JSON，不写文件。

判定（按最严原则）:
    5 项全 PASS        → 健康
    1–2 项 WARN 且无 FAIL → 亚健康
    任一项 FAIL        → 不健康

退出码: 0 健康 / 1 亚健康 / 2 不健康或执行出错
本脚本只读被检技能包，不修改其内容；报告为运行时产物，写在包外。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATE_STRUCTURE = SCRIPT_DIR / "validate_structure.py"
VALIDATE_SKILL = SCRIPT_DIR / "validate_skill.py"
CHECK_TRIGGERS = SCRIPT_DIR / "check_triggers.py"

RESOURCE_REF_RE = re.compile(
    r"(?:references|scripts|assets|examples)/[A-Za-z0-9_][A-Za-z0-9_.\-/]*")
# 步骤标题形如 "### S1 名称" 或 "### S1　名称"（全角空格）
STEP_HEADING_RE = re.compile(r"^#{2,4}\s*S(\d+)\s*[　\-.、]?\s*(\S.*)$", re.MULTILINE)
# 四要素标签
ELEMENT_RE = re.compile(r"^\s*[-*]\s*(输入|动作|产出|失败分支)\s*[:：]")
# 模糊词（对照 references/body-spec.md 第 3 节）
VAGUE_STEP_WORDS = ["必要时", "酌情", "视情况", "灵活处理", "适当", "根据实际情况"]


def run(cmd):
    """执行子命令，返回 (退出码, 标准输出)。异常不吞，记为退出码 -1。"""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    except OSError as exc:
        return -1, "调用失败：%s" % exc
    return proc.returncode, proc.stdout


def item_structure(skill_dir):
    """项目一：结构合规。"""
    rc, out = run([sys.executable, str(VALIDATE_STRUCTURE), str(skill_dir), "--json"])
    if rc == -1:
        return "FAIL", out.strip()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return "FAIL", "结构校验输出无法解析"
    s = data["summary"]
    if s["fail"] > 0:
        return "FAIL", "PASS %d / WARN %d / FAIL %d" % (s["pass"], s["warn"], s["fail"])
    if s["warn"] > 0:
        return "WARN", "PASS %d / WARN %d / FAIL %d" % (s["pass"], s["warn"], s["fail"])
    return "PASS", "PASS %d / WARN %d / FAIL %d，退出码 %d" % (
        s["pass"], s["warn"], s["fail"], rc)


def item_content(skill_dir):
    """项目二：描述合规。"""
    rc, out = run([sys.executable, str(VALIDATE_SKILL), str(skill_dir), "--json"])
    if rc == -1:
        return "FAIL", out.strip()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return "FAIL", "内容校验输出无法解析"
    s = data["summary"]
    if s["FAIL"] > 0:
        return "FAIL", "PASS %d / WARN %d / FAIL %d" % (s["PASS"], s["WARN"], s["FAIL"])
    if s["WARN"] > 0:
        return "WARN", "PASS %d / WARN %d / FAIL %d" % (s["PASS"], s["WARN"], s["FAIL"])
    return "PASS", "PASS %d / WARN %d / FAIL %d" % (s["PASS"], s["WARN"], s["FAIL"])


def item_trigger(skill_dir, phrasings, negatives):
    """项目三：触发面。原话/近义/反面三类说法全中记 PASS，2/3 记 WARN，更低记 FAIL。"""
    if not phrasings or not Path(phrasings).is_file():
        return "WARN", "未提供说法清单，跳过触发面测试（需人工补测）"
    cmd = [sys.executable, str(CHECK_TRIGGERS), "--skill", str(skill_dir),
           "--phrasings", str(phrasings)]
    if negatives and Path(negatives).is_file():
        cmd += ["--negatives", str(negatives)]
    rc, out = run(cmd)
    m = re.search(r"汇总：(\d+)/(\d+) 命中", out)
    if m:
        hits, total = int(m.group(1)), int(m.group(2))
        detail = "%d/%d 命中" % (hits, total)
        neg = re.search(r"负样本：(\d+)/(\d+) 未误触发", out)
        if neg:
            detail += "；负样本 %s/%s 未误触发" % (neg.group(1), neg.group(2))
        if hits == total:
            return "PASS", detail
        if hits == total - 1:
            return "WARN", detail
        return "FAIL", detail
    return "FAIL", "触发测试输出无法解析"


def item_samples(skill_dir, samples_dir):
    """项目四：产出抽样。检查产出目录下的 SKILL.md 是否满足四要素与字段表结构。"""
    if not samples_dir or not Path(samples_dir).is_dir():
        return "WARN", "未提供产出目录，跳过抽样（需人工抽样核对）"
    files = sorted(Path(samples_dir).rglob("SKILL.md"))
    if not files:
        return "WARN", "产出目录内无 SKILL.md，跳过抽样"
    ok = 0
    problems = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        steps = STEP_HEADING_RE.findall(text)
        issues = []
        if not steps:
            issues.append("无 S1…Sn 步骤编号")
        else:
            nums = [int(n) for n, _ in steps]
            if nums != list(range(1, len(nums) + 1)):
                issues.append("步骤编号不连续")
            for idx, _ in steps:
                block = _step_block(text, idx)
                missing = [e for e in ("输入", "动作", "产出", "失败分支")
                           if not re.search(r"^\s*[-*]\s*%s\s*[:：]" % e,
                                            block, re.MULTILINE)]
                if missing:
                    issues.append("S%s 缺四要素：%s" % (idx, "/".join(missing)))
        vague = [w for w in VAGUE_STEP_WORDS if w in text]
        if vague:
            issues.append("模糊词残留：%s" % "/".join(vague))
        if issues:
            problems.append("%s：%s" % (f.parent.name, "；".join(issues)))
        else:
            ok += 1
    total = len(files)
    if problems:
        return "FAIL", "通过 %d/%d；%s" % (ok, total, " | ".join(problems[:3]))
    return "PASS", "通过 %d/%d" % (ok, total)


def _step_block(text, idx):
    """取 S{idx} 步骤到下一个 S 之前（或下一个二级标题之前）的正文。"""
    pat = re.compile(r"^#{2,4}\s*S%s\s*[　\-.、]?\s*(\S.*)$" % idx, re.MULTILINE)
    m = pat.search(text)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^#{2,4}\s*S\d+\s*[　\-.、]?\s*\S", rest, re.MULTILINE)
    end = nxt.start() if nxt else len(rest)
    return rest[:end]


def item_freshness(skill_dir):
    """项目五：引用新鲜度。检查主文件引用的资源路径是否都存在且非空。"""
    main = Path(skill_dir) / "SKILL.md"
    if not main.is_file():
        return "FAIL", "缺少 SKILL.md"
    text = main.read_text(encoding="utf-8", errors="ignore")
    refs = sorted({m.rstrip("./,;:!?)]}'\"") for m in RESOURCE_REF_RE.findall(text)})
    missing = []
    for r in refs:
        p = Path(skill_dir) / r
        if not p.exists():
            missing.append(r)
        elif p.is_file() and p.stat().st_size == 0:
            missing.append(r + "（空文件）")
    if missing:
        return "FAIL", "过期或悬空引用 %d 条：%s" % (len(missing), ", ".join(missing[:5]))
    return "PASS", "引用 %d 条全部存在且非空" % len(refs)


def verdict_of(results):
    """按最严原则定判定。results 为 [(项目名, 状态, 证据)]。"""
    statuses = [r[1] for r in results]
    if "FAIL" in statuses:
        return "不健康"
    if "WARN" in statuses:
        return "亚健康"
    return "健康"


def build_report(skill_dir, results, verdict, action):
    main = Path(skill_dir) / "SKILL.md"
    version = ""
    name = Path(skill_dir).name
    if main.is_file():
        head = main.read_text(encoding="utf-8", errors="ignore")[:2000]
        mv = re.search(r"^version:\s*(\S+)", head, re.MULTILINE)
        if mv:
            version = mv.group(1)
    lines = [
        "# 健康度体检报告",
        "日期：%s" % date.today().isoformat(),
        "技能包：%s，version %s" % (name, version or "未声明"),
        "",
        "| # | 项目 | 结果 | 证据 |",
        "| --- | --- | --- | --- |",
    ]
    for i, (name_, status, evidence) in enumerate(results, 1):
        lines.append("| %d | %s | %s | %s |" % (i, name_, status, evidence))
    lines += ["", "判定：%s" % verdict, "处置：%s" % action, ""]
    return "\n".join(lines)


def _default_report_path(skill_dir):
    """默认报告路径：包外 tests/health_<日期>.md。

    从技能包目录向上找最近的 tests/ 目录；找不到则放在技能包同级目录，
    保证报告不进技能包（对照 references/health-check.md 第 5.2 节）。
    """
    name = "health_%s.md" % date.today().isoformat()
    cur = skill_dir.parent
    for _ in range(4):
        if cur.is_dir():
            candidate = cur / "tests"
            if candidate.is_dir():
                return candidate / name
        if cur.parent == cur:
            break
        cur = cur.parent
    return skill_dir.parent / name


def main():
    ap = argparse.ArgumentParser(description="技能健康度体检（A3）自动化")
    ap.add_argument("skill_dir", help="待检技能包目录")
    ap.add_argument("--report", help="报告输出路径（默认写包外 tests/）")
    ap.add_argument("--phrasings", help="说法清单文件")
    ap.add_argument("--negatives", help="负样本清单文件")
    ap.add_argument("--samples", help="产出抽样目录")
    ap.add_argument("--json", action="store_true", help="只输出 JSON，不写报告")
    args = ap.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    if not skill_dir.is_dir():
        sys.stderr.write("技能包目录不存在：%s\n" % skill_dir)
        return 2

    results = [
        ("结构合规",) + item_structure(skill_dir),
        ("描述合规",) + item_content(skill_dir),
        ("触发面",) + item_trigger(skill_dir, args.phrasings, args.negatives),
        ("产出抽样",) + item_samples(skill_dir, args.samples),
        ("引用新鲜度",) + item_freshness(skill_dir),
    ]
    verdict = verdict_of(results)
    action = {
        "健康": "记录归档，不改包；下次体检周期到了再查。",
        "亚健康": "逐条写保留理由，排入下次改动；修复后重跑本体检。",
        "不健康": "定位到具体文件与写法，修复后整体重跑，不许局部重跑。",
    }[verdict]

    if args.json:
        print(json.dumps({
            "skill_dir": str(skill_dir),
            "items": [{"item": n, "status": s, "evidence": e} for n, s, e in results],
            "verdict": verdict, "action": action,
        }, ensure_ascii=False, indent=2))
    else:
        print("== 健康度体检：%s ==" % skill_dir.name)
        for n, s, e in results:
            print("[%-4s] %-10s %s" % (s, n, e))
        print("判定：%s" % verdict)
        print("处置：%s" % action)

        report_path = None
        if args.report:
            report_path = Path(args.report)
        else:
            # 默认写包外 tests/：从技能包目录向上找最近的 tests/ 目录；
            # 找不到则放在技能包的同级目录，避免报告进包。
            report_path = _default_report_path(skill_dir)
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                build_report(skill_dir, results, verdict, action), encoding="utf-8")
            print("报告：%s" % report_path)
        except OSError as exc:
            sys.stderr.write("报告写入失败：%s\n" % exc)
            return 2

    return {"健康": 0, "亚健康": 1, "不健康": 2}[verdict]


if __name__ == "__main__":
    sys.exit(main())
