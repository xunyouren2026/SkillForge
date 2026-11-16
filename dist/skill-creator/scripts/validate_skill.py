#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Skill 结构校验器（仅标准库）。

用法:
    python validate_skill.py <skill-dir> [--json] [--strict]

检查项编号在 skill-creator 的 references/ 与 assets/ 中被引用，请勿随意变更:
    P001 frontmatter 结构      P002 name 规范        P003 description 存在与长度
    P004 description 人称      P005 触发语覆盖       P006 引用路径完整性
    P007 占位符残留            P008 主文件行数        P009 空泛词
    P010 排除场景              P011 目录规范          P012 资源索引表

退出码: 存在 FAIL -> 1; 否则 0 (--strict 时 WARN 也返回 1)
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

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PLACEHOLDER_RE = re.compile(r"\{\{[A-Za-z][A-Za-z0-9_-]*\}\}")
# P007 槽位式残留标记：
#   1. 通用槽位词（待补充 / 待填写 / 此处填写 / PLACEHOLDER）——本身即残留信号；
#      按整词判定：「尚待填写」「待填写区说明」这类修饰性用法不算残留。
#   2. TODO / FIXME / HACK / XXX —— 仅当处于「待填写槽位」语法位置才算残留，
#      即标记词后接冒号或行尾，且后面没有实际内容。
#      这样 `TODO-INDEX.md`、`旧 TODO 关键字`、`标注 TODO 含义` 等合法引用不误杀。
SLOT_WORDS = ("待补充", "待填写", "此处填写", "PLACEHOLDER")
# 中文槽位词按「后面不接汉字」判定：中文没有词边界，「输出待补充」这类
# 紧跟其他汉字的槽位残留必须能抓到；而「尚待填写完整」「待填写区说明」
# 这类修饰性用法后面接了汉字，放过。
SLOT_WORD_RE = re.compile(
    r"(?:待补充|待填写|此处填写)(?![一-鿿])"
    r"|(?<![A-Za-z0-9_])PLACEHOLDER(?![A-Za-z0-9_])"
)
# 槽位标记词：后接冒号 + 可选空白 + 行尾，或单独出现在行尾。
SLOT_MARKER_RE = re.compile(
    r"(?i)(?<![\w-])(TODO|FIXME|HACK|XXX)(?![\w-])\s*[:：]?\s*$"
)
# 行内代码（反引号包裹）内的标记词属于引用，不算残留。
INLINE_CODE_RE = re.compile(r"`[^`]*`")
# 代码块（围栏）内的内容属于示例，不参与残留判定。
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
QUOTED_TRIGGER_RE = re.compile(r"「([^」]+)」")
RESOURCE_REF_RE = re.compile(r"(?:references|scripts|assets|examples)/[A-Za-z0-9_][A-Za-z0-9_.\-/]*")
VAGUE_WORDS = ["帮助", "辅助", "相关", "各种", "提升效率", "智能化", "一站式", "强大的", "全方位"]
PERSON_RE = re.compile(r"(?:我可以帮你|本技能可以帮你|你可以|你能|我们将|我来|帮你|为您提供)")
BOUNDARY_WORDS = ["不覆盖", "不用于", "不涉及", "排除", "不适用于", "不处理", "不做"]
TECH_TERMS = ["skill", "技能", "description", "SKILL.md", "reference", "references/", "scripts/"]
MAX_RECOMMENDED_LINES = 300
MAX_HARD_LINES = 500


def parse_frontmatter(text: str):
    """返回 (fields, body) 或 (None, 原因)。支持单行、引号、| 与 > 块。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "首行必须为 ---"
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None, "缺少闭合的 ---"
    fields: dict[str, str] = {}
    i = 1
    while i < end:
        line = lines[i]
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val in {"|", ">", "|-", ">-"}:
                block: list[str] = []
                i += 1
                while i < end and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                    if lines[i].strip():
                        block.append(lines[i].strip())
                    i += 1
                fields[key] = " ".join(block) if val.startswith(">") else "\n".join(block)
                continue
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ("\"", "'"):
                val = val[1:-1]
            fields[key] = val
        i += 1
    return {"fields": fields, "body": "\n".join(lines[end + 1:])}, None


def add(results, code, level, message, hint=""):
    results.append({"code": code, "level": level, "message": message, "hint": hint})


def check(skill_dir: Path) -> list[dict]:
    r: list[dict] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_dir.is_dir():
        add(r, "P001", "FAIL", f"技能目录不存在：{skill_dir}")
        return r
    if not skill_md.is_file():
        add(r, "P001", "FAIL", "缺少 SKILL.md", "SKILL.md 是唯一必需文件")
        return r

    text = skill_md.read_text(encoding="utf-8")
    fm, err = parse_frontmatter(text)
    if fm is None:
        add(r, "P001", "FAIL", f"frontmatter 无效：{err}", "文件首行写 ---，并在若干行后以 --- 闭合")
        return r
    fields, body = fm["fields"], fm["body"]
    name = fields.get("name", "").strip()
    desc = fields.get("description", "").strip()
    add(r, "P001", "PASS", "frontmatter 结构完整（--- 正确包裹）")

    # P002 name
    if not name:
        add(r, "P002", "FAIL", "缺少 name", "frontmatter 中补 name: <小写连字符名>")
    elif not NAME_RE.match(name) or len(name) > 64:
        add(r, "P002", "FAIL", f"name 不规范：{name!r}", "仅小写字母/数字/连字符，≤64 字符，如 classical-mechanics-solver")
    elif name != skill_dir.name:
        add(r, "P002", "WARN", f"name({name}) 与目录名({skill_dir.name}) 不一致", "改名或改 name，保持一致以便分发")
    else:
        add(r, "P002", "PASS", f"name 规范且与目录名一致：{name}")

    # P003 description 存在与长度
    if not desc:
        add(r, "P003", "FAIL", "缺少 description", "description 是检索主字段，不可省略")
    elif len(desc) > 1024:
        add(r, "P003", "FAIL", f"description 长度 {len(desc)} > 1024", "压缩为三段式，细节移到正文")
    elif "\n" in desc:
        add(r, "P003", "WARN", "description 含换行（块标量）", "建议压成单行，避免解析差异")
    else:
        add(r, "P003", "PASS", f"description 单行，{len(desc)} 字符")

    # P004 人称
    # 「」内是收录的用户原话触发语，本就含「帮我」「我想」等第一/第二人称措辞，
    # 属于合法内容；先剔除触发语再做人称判定，避免误报。
    if desc:
        desc_for_person = QUOTED_TRIGGER_RE.sub("", desc)
        hit = PERSON_RE.search(desc_for_person)
        if hit:
            add(r, "P004", "FAIL", f"description 叙述部分含第一/第二人称：{hit.group()!r}",
                "改为第三人称，如「把…转成…」；「」内的用户原话不受此限")
        else:
            add(r, "P004", "PASS", "description 叙述部分为第三人称 / 无主句（触发语原话已豁免）")

    # P005 触发语
    if desc:
        triggers = QUOTED_TRIGGER_RE.findall(desc)
        non_tech = [t for t in triggers if not any(k.lower() in t.lower() for k in TECH_TERMS)]
        if len(triggers) < 3:
            add(r, "P005", "FAIL", f"「」用户原话触发语仅 {len(triggers)} 条（需 ≥3）",
                "从需求卡取用户原话，覆盖口语/术语/无术语三类，见 references/description-writing.md")
        elif not non_tech:
            add(r, "P005", "FAIL", "触发语全为术语型，缺少口语/无术语型说法",
                "补一条不含 Skill/技能/description 的用户原话，如「下次别让我从头讲一遍」")
        else:
            add(r, "P005", "PASS", f"触发语 {len(triggers)} 条，其中非术语型 {len(non_tech)} 条")
        has_object = bool(re.search(r"\.md|\.py|\.txt|\.xlsx|\.csv|references/|scripts/|assets/|SKILL", desc))
        if not has_object:
            add(r, "P005", "WARN", "description 未见明确可识别对象", "补文件扩展名/领域术语/命令名，提升检索区分度")

    # P006 引用路径完整性
    refs = sorted(set(RESOURCE_REF_RE.findall(body)))
    missing = []
    checked = 0
    for ref in refs:
        rel = ref.rstrip("/")
        target = skill_dir / rel
        if rel.endswith("/") or rel in {"references", "scripts", "assets", "examples"}:
            if not target.is_dir():
                missing.append(rel + "/（目录）")
            checked += 1
            continue
        checked += 1
        if not target.exists():
            missing.append(rel)
    if missing:
        add(r, "P006", "FAIL", f"引用了 {len(missing)} 个不存在的路径：{', '.join(missing[:5])}",
            "补齐文件，或删除主文件中无法解析的引用")
    else:
        add(r, "P006", "PASS", f"正文引用的 {checked} 个资源路径均存在")

    # P007 占位符 / 槽位残留
    ph = sorted(set(PLACEHOLDER_RE.findall(body)))
    # 槽位式残留判定：逐行检查，去掉行内代码与围栏代码块后再匹配，
    # 避免把 `TODO-INDEX.md`、说明句里的 TODO 等合法引用误判为残留。
    slot_hits = []
    for no, raw_line in enumerate(body.splitlines(), 1):
        line = FENCE_RE.sub("", raw_line)
        line = INLINE_CODE_RE.sub("", line)
        words = sorted(set(SLOT_WORD_RE.findall(line)))
        m = SLOT_MARKER_RE.search(line)
        if m:
            words.append(m.group(1))
        if words:
            slot_hits.append((no, words))
    if ph or slot_hits:
        detail = (f"占位符 {ph[:5]}" if ph else "")
        if slot_hits:
            detail += ("  " if detail else "") + "槽位残留 " + ", ".join(
                "第%d行:%s" % (no, "/".join(words)) for no, words in slot_hits[:5])
        add(r, "P007", "FAIL", f"交付物存在未替换内容：{detail.strip()}",
            "替换全部 {{...}} 占位符与槽位标记，模板文件属于 assets/ 不参与本检查")
    else:
        add(r, "P007", "PASS", "无 {{...}} 占位符、无槽位残留（TODO 等标记词的合法引用不误报）")

    # P008 行数
    line_count = len(text.splitlines())
    if line_count > MAX_HARD_LINES:
        add(r, "P008", "FAIL", f"SKILL.md {line_count} 行 > 硬上限 {MAX_HARD_LINES}",
            "按 references/directory-design.md 拆分，主文件只留路由与关键约束")
    elif line_count > MAX_RECOMMENDED_LINES:
        add(r, "P008", "WARN", f"SKILL.md {line_count} 行 > 建议 {MAX_RECOMMENDED_LINES}",
            "评估是否可把长表/长清单外置到 references/")
    else:
        add(r, "P008", "PASS", f"SKILL.md {line_count} 行，在预算内")

    # P009 空泛词
    if desc:
        vague = [w for w in VAGUE_WORDS if w in desc]
        if vague:
            add(r, "P009", "FAIL", f"description 含空信息词：{vague}", "替换为具体动词 + 对象 + 产出")
        else:
            add(r, "P009", "PASS", "description 无空信息词")

    # P010 排除场景
    if desc:
        if not any(w in desc for w in BOUNDARY_WORDS):
            add(r, "P010", "FAIL", "description 缺排除场景，易误触发/抢触发", "补「不覆盖…」「不用于…」")
        else:
            add(r, "P010", "PASS", "description 含排除场景")

    # P011 目录规范
    problems = []
    for sub in ("references", "scripts", "assets", "examples"):
        d = skill_dir / sub
        if d.is_dir() and not any(d.iterdir()):
            problems.append(f"空目录 {sub}/")
    for d in sorted(p for p in skill_dir.iterdir() if p.is_dir()):
        if d.name not in {"references", "scripts", "assets", "examples", "__pycache__"}:
            problems.append(f"非标准目录 {d.name}/")
    if problems:
        add(r, "P011", "WARN", "；".join(problems), "移除空目录；测试目录应放工作区顶层 tests/，不放技能包内")
    else:
        add(r, "P011", "PASS", "目录规范，技能包内无空目录、无测试目录")

    # P012 资源索引表
    if body.count("| `") >= 3 or "资源索引" in body:
        add(r, "P012", "PASS", "存在资源索引 / 加载路由表")
    else:
        add(r, "P012", "WARN", "未见资源索引表", "有 references/ 时写明「何时加载哪一个」，支持渐进披露")

    return r


def main() -> int:
    ap = argparse.ArgumentParser(description="Skill 结构校验器")
    ap.add_argument("skill_dir", help="待校验的技能目录")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--strict", action="store_true", help="WARN 也视为失败")
    args = ap.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    results = check(skill_dir)
    counts = {lv: sum(1 for x in results if x["level"] == lv) for lv in ("PASS", "WARN", "FAIL")}

    if args.json:
        print(json.dumps({"skill_dir": str(skill_dir), "summary": counts, "checks": results},
                         ensure_ascii=False, indent=2))
    else:
        print(f"== 结构校验：{skill_dir.name} ==")
        for x in results:
            print(f"[{x['level']:<4}] {x['code']}  {x['message']}")
            if x["hint"] and x["level"] != "PASS":
                print(f"         → {x['hint']}")
        print(f"-- 汇总：PASS {counts['PASS']} / WARN {counts['WARN']} / FAIL {counts['FAIL']} --")
        print("判定：" + ("可交付" if counts["FAIL"] == 0 else "不可交付，请修复 FAIL 后重跑"))

    failed = counts["FAIL"] > 0 or (args.strict and counts["WARN"] > 0)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
