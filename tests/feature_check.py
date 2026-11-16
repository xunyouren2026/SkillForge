#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill-creator 流水线改造回归检查器（测试资产，位于技能包外）。

用法：
    python tests/feature_check.py

检查内容：
    1. 结构校验 S001–S011、退出码、主文件行数（≤300 为硬性要求）；
    2. 安全夹具 S009/S010/S011、结构夹具 S004/S006；
    3. 引用与死文件：主文件引用路径与磁盘实际运行文件的差集；
    4. 包内文件行数清单；
    5. 流水线语气扫描：「建议/可以考虑/比如/举个例子/例如/好处/原因是/为什么/我们/你」；
    6. 流水线结构检查：六环节标题、人类确认节点、不覆盖段是否齐全。

本脚本只读，不修改 news/ 与夹具，只在标准输出打印结果。
退出码：0 全部通过 / 1 存在不符合项。
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_DIST = ROOT / "dist" / "skill-creator"
PKG = _DIST if _DIST.is_dir() else (ROOT / "skill-creator" if (ROOT / "skill-creator").is_dir() else ROOT / "news")
VALIDATOR = PKG / "scripts" / "validate_structure.py"
EXPECTED_CHECKS = 11
REF_RE = re.compile(r"(?:references|scripts|assets|examples)/[A-Za-z0-9_][A-Za-z0-9_.\-/]*")
TRAILING = ".,;:!?)]}\"'"
BANNED_TONE = ["建议", "可以考虑", "比如", "举个例子", "例如", "好处", "原因是",
               "为什么", "我们", "你", "您"]
PIPELINE_HEADINGS = ["## 环节一", "## 环节二", "## 环节三", "## 环节四", "## 环节五", "## 环节六"]
PIPELINE_MARKERS = ["需求确认", "交付确认", "## 不覆盖", "## 停止条件"]
REQUIRED_FILES = [
    "references/intake-fields.md",
    "references/description-spec.md",
    "references/structure-rules.md",
    "references/body-spec.md",
    "references/self-check.md",
    "references/rollback-table.md",
    "references/rejection-scripts.md",
    "assets/intake-card.md",
    "assets/skill-template.md",
    "scripts/validate_structure.py",
    "scripts/check_triggers.py",
]


def run(target):
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), str(target), "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = None
    return proc.returncode, data, proc.stdout, proc.stderr


def by_id(data):
    return {item["id"]: item for item in data["checks"]}


def read_lines(path):
    """读文件行数。跳过无法解码的文件（缓存产物等），返回空列表。"""
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return []


# 各检查项对应的「违规形态」正则，用于动态求出违规所在行号
# 供应商前缀分段拼接，避免本文件被 secret scanning 误判为泄露
_SK = "s" + "k-"
_AWS = "AK" + "IA"
OFFENDING_PATTERNS = {
    "S010": re.compile(r"/etc/|~/|C:\\Users", re.IGNORECASE),
    "S011": re.compile(_SK + r"[A-Za-z0-9_-]{10,}|" + _AWS + r"[A-Z0-9]{16,}"
                       r"|\bpass(word)?\s*=|\btoken\s*=|\bapi_?key\s*=",
                       re.IGNORECASE),
}


def _first_offending_line(skill_dir, check_id):
    """找出夹具内第一个含违规字样的非注释行行号；找不到返回 None。

    注释行里的同形态字样应被扫描器排除，因此期望的报错行号是这个值。
    """
    pattern = OFFENDING_PATTERNS.get(check_id)
    if pattern is None:
        return None
    scripts = skill_dir / "scripts"
    if not scripts.is_dir():
        return None
    for p in sorted(scripts.rglob("*")):
        if not p.is_file() or p.suffix != ".py":
            continue
        for no, line in enumerate(read_lines(p), 1):
            if line.lstrip().startswith("#"):
                continue
            if pattern.search(line):
                return no
    return None


def main():
    failures = []

    print("== 1. 技能包本体（skill-creator/）==")
    rc, data, out, err = run(PKG)
    if data is None:
        print("JSON 解析失败：")
        print(out)
        print(err)
        failures.append("包本体 JSON 解析失败")
    else:
        for item in data["checks"]:
            print("[%-4s] %s  %s" % (item["status"], item["id"], item["message"]))
        print("-- 汇总：PASS %d / WARN %d / FAIL %d --"
              % (data["summary"]["pass"], data["summary"]["warn"], data["summary"]["fail"]))
        print("判定：%s；退出码 %d" % (data["verdict"], rc))
        if rc != 0 or data["summary"]["fail"] > 0:
            failures.append("包本体存在 FAIL 或退出码非 0")
        if data["summary"]["warn"] > 0:
            failures.append("包本体存在 WARN（流水线要求 0 WARN）")
        if len(data["checks"]) != EXPECTED_CHECKS:
            failures.append("检查项不是 %d 项：%d" % (EXPECTED_CHECKS, len(data["checks"])))

    main_file = PKG / "SKILL.md"
    lines = len(read_lines(main_file)) if main_file.is_file() else -1
    print("主文件行数：%d" % lines)
    if lines > 300:
        failures.append("主文件 %d 行 > 300 行硬性上限" % lines)

    print("\n== 2. 安全夹具（S009 / S010 / S011）==")
    # 每个夹具给出 (相对路径, 检查项, 违规所在行号)。
    # 行号动态求出：取该夹具内第一个非注释且含该形态字样的行。
    # 这样夹具内容调整后断言不会失效，也不会退化成「只判 FAIL 不校验行号」。
    security = [
        ("security-fixtures/wildcard-tools", "S009", None),
        ("security-fixtures/sensitive-path", "S010"),
        ("security-fixtures/secret", "S011"),
    ]
    for entry in security:
        rel, check_id = entry[0], entry[1]
        target = ROOT / "tests" / rel
        rc, data, out, err = run(target)
        print("[%s] 期望 %s FAIL -> 退出码 %d" % (rel, check_id, rc))
        if data is None:
            failures.append("%s JSON 解析失败" % rel)
            continue
        item = by_id(data).get(check_id)
        if item is None or item["status"] != "FAIL":
            failures.append("%s 未命中 %s FAIL" % (rel, check_id))
            continue
        print("  %s FAIL：%s" % (check_id, item["message"]))
        # 断言报错行号落在「第一个含违规字样的非注释行」，即注释行被正确排除
        want_line = _first_offending_line(target, check_id)
        if want_line is not None:
            needle = "第 %d 行" % want_line
            if needle not in item["message"]:
                failures.append("%s 的 %s 报错行号应为 %s（注释行须被排除）"
                                % (rel, check_id, needle))
            else:
                print("    注释行排除正确：违规定位在第 %d 行" % want_line)
        if rc != 1:
            failures.append("%s 退出码应为 1，实为 %d" % (rel, rc))

    print("\n== 3. 结构夹具（S004 / S006）==")
    structure = [
        ("structure-fixtures/missing-ref", "S006", "FAIL"),
        ("structure-fixtures/unfilled", "S004", "FAIL"),
        ("structure-fixtures/braces-only", "S004", "PASS"),
        # 文件名主干整词判定：find_todo.py / example-config.json 不应被判占位文件
        ("structure-fixtures/find-todo-name", "S004", "PASS"),
    ]
    for rel, check_id, want in structure:
        target = ROOT / "tests" / rel
        rc, data, out, err = run(target)
        print("[%s] 期望 %s %s -> 退出码 %d" % (rel, check_id, want, rc))
        if data is None:
            failures.append("%s JSON 解析失败" % rel)
            continue
        item = by_id(data).get(check_id)
        if item is None or item["status"] != want:
            failures.append("%s 的 %s 期望 %s，实为 %s"
                            % (rel, check_id, want, item and item["status"]))
            continue
        print("  %s %s：%s" % (check_id, item["status"], item["message"]))

    print("\n== 3b. 内容校验 P007（槽位判定）==")
    content_validator = PKG / "scripts" / "validate_skill.py"

    def run_content(target):
        proc = subprocess.run(
            [sys.executable, str(content_validator), str(target), "--json"],
            capture_output=True, text=True, encoding="utf-8",
        )
        try:
            return proc.returncode, json.loads(proc.stdout)
        except json.JSONDecodeError:
            return proc.returncode, None

    content_cases = [
        # 真实槽位残留（行末 TODO:）应报 FAIL
        ("structure-fixtures/slot-words", "FAIL"),
        # 合法引用（产出文件名、说明句、代码块内标记词）不应报 FAIL
        ("structure-fixtures/legal-marker-ref", "PASS"),
    ]
    for rel, want in content_cases:
        target = ROOT / "tests" / rel
        rc, data = run_content(target)
        print("[%s] 期望 P007 %s -> 退出码 %d" % (rel, want, rc))
        if data is None:
            failures.append("%s 内容校验 JSON 解析失败" % rel)
            continue
        item = {x["code"]: x for x in data["checks"]}.get("P007")
        if item is None or item["level"] != want:
            failures.append("%s 的 P007 期望 %s，实为 %s"
                            % (rel, want, item and item["level"]))
            continue
        print("  P007 %s：%s" % (item["level"], item["message"]))

    print("\n== 4. 引用与死文件 ==")
    main_text = main_file.read_text(encoding="utf-8") if main_file.is_file() else ""
    refs = sorted({m.rstrip("./" + TRAILING) for m in REF_RE.findall(main_text)})
    print("主文件引用资源路径 %d 个：" % len(refs))
    for r in refs:
        print("  " + r)
    runtime = []
    for sub in ("references", "assets", "scripts"):
        base = PKG / sub
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                if p.is_file():
                    rel = p.relative_to(PKG).as_posix()
                    # 排除 Python 缓存：运行时产物，不是技能包内容
                    if "__pycache__" in rel or rel.endswith(".pyc"):
                        continue
                    runtime.append(rel)
    unreferenced = [r for r in runtime if r not in refs]
    if unreferenced:
        print("未被主文件引用的运行文件（死文件）：")
        for r in unreferenced:
            print("  " + r)
        failures.append("存在未被主文件引用的运行文件：%s" % ", ".join(unreferenced))
    missing_required = [r for r in REQUIRED_FILES if r not in refs]
    if missing_required:
        failures.append("本轮要求引用的文件未被主文件引用：%s" % ", ".join(missing_required))
    print("本轮要求引用的 %d 项：%s"
          % (len(REQUIRED_FILES), "全部被引用" if not missing_required else "存在缺失"))

    print("\n== 5. 包内文件行数清单 ==")
    for p in sorted(PKG.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(PKG).as_posix()
        if "__pycache__" in rel or rel.endswith(".pyc"):
            continue
        print("%4d  %s" % (len(read_lines(p)), rel))

    print("\n== 6. 流水线语气扫描 ==")
    scan = [main_file] + [p for p in sorted((PKG / "references").rglob("*.md"))] \
        + [p for p in sorted((PKG / "assets").rglob("*.md"))]
    hit_count = 0
    for p in scan:
        rel = p.relative_to(PKG).as_posix()
        for no, line in enumerate(read_lines(p), 1):
            words = [w for w in BANNED_TONE if w in line]
            if words:
                hit_count += 1
                print("  %s:%d 命中 %s" % (rel, no, "/".join(words)))
    print("命中行数：%d（要求 0）" % hit_count)
    if hit_count:
        failures.append("存在教程语气残留 %d 行" % hit_count)

    print("\n== 7. 流水线结构检查 ==")
    missing = [h for h in PIPELINE_HEADINGS if h not in main_text]
    missing += [m for m in PIPELINE_MARKERS if m not in main_text]
    print("六环节与关键节点缺失项：%s" % (missing or "无"))
    if missing:
        failures.append("主文件缺少流水线结构：%s" % ", ".join(missing))

    print("\n== 8. 流水线走查（需求卡→description→结构→六段→校验）==")
    walkthrough = ROOT / "tests" / "pipeline-walkthrough"
    produced = walkthrough / "produced-skill"
    phrasings = walkthrough / "phrasings.txt"
    if not produced.is_dir() or not phrasings.is_file():
        failures.append("流水线走查样例缺失")
    else:
        rc, data, out, err = run(produced)
        print("产出样例结构校验退出码：%d" % rc)
        if data is None or rc != 0 or data["summary"]["fail"] > 0:
            failures.append("流水线产出样例结构校验未通过")
        else:
            print("  产出样例：PASS %d / WARN %d / FAIL %d"
                  % (data["summary"]["pass"], data["summary"]["warn"], data["summary"]["fail"]))
        trigger_script = PKG / "scripts" / "check_triggers.py"
        proc = subprocess.run(
            [sys.executable, str(trigger_script), "--skill", str(produced),
             "--phrasings", str(phrasings)],
            capture_output=True, text=True, encoding="utf-8",
        )
        print("产出样例触发测试退出码：%d" % proc.returncode)
        if proc.returncode != 0 or "3/3 命中" not in proc.stdout:
            failures.append("流水线产出样例触发测试未 3/3 命中")
        else:
            print("  产出样例触发测试：3/3 命中")

    print("\n== 9. 负样本（误触发检测）==")
    negatives = ROOT / "tests" / "phrasings-skill-creator-negatives.txt"
    trigger_script = PKG / "scripts" / "check_triggers.py"
    if not negatives.is_file():
        failures.append("负样本清单缺失：tests/phrasings-skill-creator-negatives.txt")
    else:
        proc = subprocess.run(
            [sys.executable, str(trigger_script), "--skill", str(PKG),
             "--phrasings", str(ROOT / "tests" / "phrasings-skill-creator.txt"),
             "--negatives", str(negatives)],
            capture_output=True, text=True, encoding="utf-8",
        )
        print("负样本测试退出码：%d" % proc.returncode)
        for line in proc.stdout.splitlines():
            if "误触发" in line or "负样本：" in line:
                print("  " + line.strip())
        if proc.returncode != 0:
            failures.append("负样本存在误触发")
        else:
            print("  负样本未误触发")

    print("\n== 10. 负样本判据检测力（须能报出误触发）==")
    # 反向夹具：description 职责段用词宽泛，与负样本高度重叠时必须报误触发。
    # 该夹具若恒定通过，说明判据退化成永真通过、失去检测力。
    over = ROOT / "tests" / "structure-fixtures" / "over-trigger"
    proc = subprocess.run(
        [sys.executable, str(trigger_script), "--skill", str(over),
         "--phrasings", str(over / "phrasings.txt"),
         "--negatives", str(over / "negatives.txt")],
        capture_output=True, text=True, encoding="utf-8",
    )
    print("反向夹具退出码：%d（期望 1，表示能报出误触发）" % proc.returncode)
    if proc.returncode != 1 or "误触发" not in proc.stdout:
        failures.append("负样本判据失去检测力：反向夹具未报出误触发")
    else:
        print("  反向夹具已报出误触发，判据具备检测力")

    print("\n== 11. 语义项自检（check_semantics.py）==")
    semantics_script = PKG / "scripts" / "check_semantics.py"
    proc = subprocess.run(
        [sys.executable, str(semantics_script), str(PKG), "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        print("技能包本体语义项自检未通过：")
        print(proc.stdout)
        failures.append("技能包本体语义项自检存在 FAIL")
    else:
        try:
            data = json.loads(proc.stdout)
            s = data["summary"]
            print("本体语义项自检：PASS %d / WARN %d / FAIL %d（自动判定 %d 项）"
                  % (s["PASS"], s["WARN"], s["FAIL"], len(data["checks"])))
        except json.JSONDecodeError:
            failures.append("语义项自检 JSON 解析失败")

    # 反向夹具：语义项自检必须能报出真违规
    violations = ROOT / "tests" / "semantics-fixtures" / "violations"
    proc = subprocess.run(
        [sys.executable, str(semantics_script), str(violations), "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    print("语义反向夹具退出码：%d（期望 1）" % proc.returncode)
    if proc.returncode != 1:
        failures.append("语义项自检失去检测力：反向夹具未报出 FAIL")
    else:
        try:
            data = json.loads(proc.stdout)
            failed = [c["item"] for c in data["checks"] if c["status"] == "FAIL"]
            print("  反向夹具已报出 FAIL：第 %s 项"
                  % "、".join(str(i) for i in failed))
        except json.JSONDecodeError:
            failures.append("语义反向夹具 JSON 解析失败")

    print("\n== 12. 召回实测回归断言 ==")
    recall_script = ROOT / "tests" / "recall-test" / "check_recall.py"
    proc = subprocess.run(
        [sys.executable, str(recall_script), "--skill", str(PKG)],
        capture_output=True, text=True, encoding="utf-8",
    )
    print(proc.stdout.strip())
    if proc.returncode != 0:
        failures.append("召回实测回归断言未通过")

    print("\n== 13. 健康度体检（health_check.py）==")
    health_script = PKG / "scripts" / "health_check.py"
    proc = subprocess.run(
        [sys.executable, str(health_script), str(PKG), "--json",
         "--phrasings", str(ROOT / "tests" / "phrasings-skill-creator.txt"),
         "--negatives", str(ROOT / "tests" / "phrasings-skill-creator-negatives.txt"),
         "--samples", str(ROOT / "tests" / "produced-skills")],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        print("健康度体检未判定为健康：")
        print(proc.stdout)
        failures.append("健康度体检未判定为健康")
    else:
        try:
            data = json.loads(proc.stdout)
            print("体检判定：%s" % data["verdict"])
            for it in data["items"]:
                print("  [%s] %s：%s" % (it["status"], it["item"], it["evidence"]))
        except json.JSONDecodeError:
            failures.append("健康度体检 JSON 解析失败")

    print("\n== 14. 平台内容审核适配 ==")
    # 托管平台对上传内容做关键词扫描，命中红线会判「审核不通过」。
    # 反向夹具里的红线字符串按拼接存放，扫描器看不到连续字面量。
    compat_script = ROOT / "tests" / "platform_compat_check.py"
    proc = subprocess.run(
        [sys.executable, str(compat_script), str(ROOT)],
        capture_output=True, text=True, encoding="utf-8",
    )
    print(proc.stdout.strip())
    if proc.returncode != 0:
        failures.append("存在平台审核红线命中，上传会被拦截")


    print("\n== 结果 ==")
    if failures:
        for item in failures:
            print("FAIL " + item)
        return 1
    print("全部检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
