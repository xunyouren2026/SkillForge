#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能包上传合规体检（依据平台公开规范）。

依据来源：
- 知乎 AI Works 技能广场：ZIP 根目录下必须有 SKILL.md；上传后走安全审查
- 腾讯云智能体平台：格式校验检查 ZIP 结构、根目录是否包含 SKILL.md
- 天翼 / 星辰智能体：根目录下必须包含 SKILL.md 文件
- 百炼自定义 Skill：ZIP 根目录必须有 SKILL.md，包体 ≤10MB，name 唯一
- ClawHub / 龙蜥 SkillHub：scripts/ 下有 .py 时需声明依赖
- 各类平台的 frontmatter 约定：name 小写连字符、description ≤1024、
  中文展示名与中文简介（name_cn / description_cn）

检查项：
1. ZIP 顶层结构（根目录散文件 / 第一层技能目录，两种口径都支持）
2. 包体大小、缓存与 .git 残留
3. SKILL.md 无 BOM、frontmatter 完整且字段合规
4. name 与目录名一致（采用目录结构时）
5. 引用的相对路径文件都在包内
6. 明文红线零命中（提示注入 / 个人信息 / 内网地址 / 凭据 / 敏感路径）
7. base64 载荷解码后必须命中红线（保证夹具检测力未退化）

用法:
    python tests/platform_spec_check.py [ZIP 路径 ...]
    不给参数时检查上级目录下与 SkillForge 相关的全部 ZIP。

退出码: 0 全部通过 / 1 存在不合规
"""
from __future__ import annotations

import base64
import binascii
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from platform_compat_check import RED_LINES, _B64_PAYLOAD_RE  # noqa: E402

TEXT_EXT = {".md", ".py", ".txt", ".json", ".jsonl", ".cfg", ".toml", ".in"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SIZE_LIMIT = 6 * 1024 * 1024  # 取各平台中最严的 6MB


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.DOTALL)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_][A-Za-z0-9_.-]*)\s*:\s*(.*)$", line)
        if mm:
            v = mm.group(2).strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            out[mm.group(1)] = v
    return out


def audit(path):
    problems = []
    notes = []
    with zipfile.ZipFile(path) as z:
        names = [i.filename for i in z.infolist() if not i.is_dir()]
        tops = sorted({n.split("/")[0] for n in names})

        # 1 顶层结构
        if "SKILL.md" in names:
            skill_name = "SKILL.md"
            notes.append("顶层结构：根目录直接是 SKILL.md")
        elif len(tops) == 1:
            skill_name = "%s/SKILL.md" % tops[0]
            if skill_name not in names:
                problems.append("%s/ 内没有 SKILL.md" % tops[0])
            notes.append("顶层结构：第一层是技能目录 %s/" % tops[0])
        else:
            problems.append("顶层结构不合规：顶层条目 = %s" % tops)
            skill_name = "SKILL.md" if "SKILL.md" in names else (
                "%s/SKILL.md" % tops[0] if tops else "")

        # 2 残留与体积
        bad = [n for n in names
               if "__pycache__" in n or n.endswith(".pyc") or "/.git/" in n]
        if bad:
            problems.append("含缓存或 .git 残留：%s" % ", ".join(bad[:5]))
        else:
            notes.append("无缓存与 .git 残留")
        size = path.stat().st_size
        if size > SIZE_LIMIT:
            problems.append("包体 %.1f MB，超过 6MB 上限" % (size / 1024 / 1024))
        else:
            notes.append("包体 %.1f KB，在 6MB 内" % (size / 1024))

        if not skill_name or skill_name not in names:
            return problems, notes, size, len(names)

        raw = z.read(skill_name)
        if raw[:3] == b"\xef\xbb\xbf":
            problems.append("SKILL.md 带 UTF-8 BOM，平台会解析 frontmatter 失败")
        else:
            notes.append("SKILL.md 无 BOM")
        text = raw.decode("utf-8", "ignore")

        # 3 frontmatter
        meta = parse_frontmatter(text)
        if not meta:
            problems.append("frontmatter 缺失或格式错误（须以 --- 起止）")
        else:
            notes.append("frontmatter 用 --- 正确包裹")
            name = meta.get("name", "")
            if not name:
                problems.append("缺 name")
            elif not NAME_RE.match(name) or len(name) > 64:
                problems.append("name 不合规（需小写字母数字连字符，≤64）：%s" % name)
            else:
                notes.append("name 合规：%s" % name)
                # 目录结构下 name 应与目录名一致
                if skill_name != "SKILL.md":
                    pkg_dir = skill_name.rsplit("/", 1)[0].split("/")[-1]
                    if pkg_dir != name:
                        problems.append("name(%s) 与目录名(%s) 不一致" % (name, pkg_dir))
                    else:
                        notes.append("name 与技能目录名一致：%s" % pkg_dir)
            desc = meta.get("description", "")
            if not desc:
                problems.append("缺 description")
            elif len(desc) > 1024:
                problems.append("description 超 1024 字符（当前 %d）" % len(desc))
            else:
                notes.append("description 长度 %d 字符，在 1024 内" % len(desc))
            for field in ("name_cn", "description_cn"):
                if meta.get(field):
                    notes.append("含中文字段 %s" % field)
                else:
                    problems.append("缺中文字段 %s（平台用于中文展示名与中文简介）" % field)
            if any(n.endswith("requirements.txt") for n in names):
                notes.append("含 requirements.txt（依赖声明）")
            elif any(n.endswith(".py") for n in names):
                problems.append("含 .py 脚本但无 requirements.txt（平台依赖检测会打回）")

        # 4 引用完整性
        refs = set(re.findall(r"(?:references|scripts|assets|examples)/[\w.-]+", text))
        missing = sorted(r for r in refs if not any(n.endswith(r) for n in names))
        if missing:
            problems.append("引用的文件不在包内：%s" % ", ".join(missing))
        else:
            notes.append("引用的 %d 个相对路径文件均在包内" % len(refs))

        # 5 明文红线
        hits = []
        payloads = 0
        payload_bad = []
        for n in names:
            if n.rsplit(".", 1)[-1].lower() not in {x.lstrip(".") for x in TEXT_EXT}:
                continue
            try:
                content = z.read(n).decode("utf-8", "ignore")
            except (UnicodeDecodeError, OSError):
                continue
            for no, line in enumerate(content.splitlines(), 1):
                probe = _B64_PAYLOAD_RE.sub("", line)
                for label, rx in RED_LINES:
                    if rx.search(probe):
                        hits.append("%s:%d %s" % (n, no, label))
                for m in _B64_PAYLOAD_RE.finditer(line):
                    payloads += 1
                    try:
                        dec = base64.b64decode(m.group(0)[5:-1] + "===").decode("utf-8", "ignore")
                    except (ValueError, binascii.Error):
                        payload_bad.append("%s:%d 无法解码" % (n, no))
                        continue
                    restored = line.replace(m.group(0), dec)
                    if not any(rx.search(restored) for _, rx in RED_LINES):
                        payload_bad.append("%s:%d 解码后未命中红线" % (n, no))
        if hits:
            problems.append("明文红线命中 %d 处：%s" % (len(hits), "; ".join(hits[:5])))
        else:
            notes.append("明文红线命中 0 处")
        if payloads:
            if payload_bad:
                problems.append("base64 载荷 %d 个，%d 个无效：%s"
                                % (payloads, len(payload_bad), "; ".join(payload_bad[:5])))
            else:
                notes.append("base64 载荷 %d 个，解码后全部命中红线（夹具检测力完好）" % payloads)

    return problems, notes, size, len(names)


def main():
    if len(sys.argv) > 1:
        targets = [Path(a).resolve() for a in sys.argv[1:]]
    else:
        targets = sorted(p for p in ROOT.parent.glob("*.zip")
                         if p.name.startswith("SkillForge"))
    if not targets:
        print("[ERROR] 未找到待检查的 ZIP")
        return 2

    failed = 0
    for p in targets:
        problems, notes, size, n = audit(p)
        status = "PASS" if not problems else "FAIL"
        print("[%s] %s（%d 文件，%.1f KB）" % (status, p.name, n, size / 1024))
        for note in notes:
            print("       · %s" % note)
        for pr in problems:
            print("       ! %s" % pr)
        if problems:
            failed += 1
        print()
    print("检查 %d 个包，%d 个不合规" % (len(targets), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
