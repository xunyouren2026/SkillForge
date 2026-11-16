#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描仓库内待办类注释（FIXME / HACK / XXX / BUG / NOTE / 旧 TODO），
输出 TODO-INDEX.md（相对仓库根的相对路径）。仅标准库，Python 3.8+。

用法：python scripts/scan_todos.py <仓库根目录>
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

MARKER_RE = re.compile(r"\b(FIXME|HACK|XXX|BUG|NOTE|TODO)\b[\s:：](.*)", re.IGNORECASE)
PRIORITY_KEYWORDS = [
    (re.compile(r"\bP0\b|\bURGENT\b|\bCRITICAL\b", re.IGNORECASE), "P0"),
    (re.compile(r"\bP1\b|\bHIGH\b", re.IGNORECASE), "P1"),
    (re.compile(r"\bP2\b|\bMEDIUM\b|\bMID\b", re.IGNORECASE), "P2"),
    (re.compile(r"\bP3\b|\bLOW\b", re.IGNORECASE), "P3"),
]
TYPE_KEYWORDS = [
    (re.compile(r"\bbug\b|\bfix\b|\bcrash\b|\b崩溃\b|\b错误\b"), "bugfix"),
    (re.compile(r"\brefactor\b|\brework\b|\bcleanup\b|\b重构\b|\b整理\b"), "refactor"),
    (re.compile(r"\bfeature\b|\bnew\b|\badd\b|\b新增\b|\b功能\b"), "feature"),
    (re.compile(r"\bquestion\b|\bwhy\b|\bwonder\b|\b疑问\b|\b为什么\b"), "question"),
]
AUTHOR_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)")
PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

DEFAULT_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".go", ".rs", ".java", ".cpp", ".c", ".h",
    ".cs", ".rb", ".php", ".swift", ".kt", ".scala", ".sh", ".bash", ".zsh",
    ".vue", ".svelte", ".md", ".html", ".css", ".scss", ".sql", ".lua", ".r",
}
EXCLUDE_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "vendor", "dist", "build",
    ".next", ".nuget", "__pycache__", ".venv", "venv", ".idea", ".vscode",
    "target", "bin", "obj", "Pods",
}


def detect_priority(body: str) -> str:
    for rx, label in PRIORITY_KEYWORDS:
        if rx.search(body):
            return label
    return "P2"


def detect_type(body: str) -> str:
    for rx, label in TYPE_KEYWORDS:
        if rx.search(body):
            return label
    return ""


def scan_file(path: Path, root: Path):
    rel = str(path.relative_to(root)).replace("\\", "/")
    skipped = []
    hits = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            skipped.append(rel)
            return hits, skipped
    except OSError:
        skipped.append(rel)
        return hits, skipped

    for lineno, line in enumerate(text.splitlines(), 1):
        m = MARKER_RE.search(line)
        if not m:
            continue
        body = m.group(0).strip()
        prio = detect_priority(body)
        typ = detect_type(body)
        am = AUTHOR_RE.search(body)
        author = "@" + am.group(1) if am else ""
        hits.append({
            "file": rel, "line": lineno, "body": body,
            "priority": prio, "type": typ, "author": author,
        })
    return hits, skipped


def walk_repo(root: Path):
    all_hits = []
    all_skipped = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            path = Path(dirpath) / fn
            if path.suffix.lower() not in DEFAULT_SUFFIXES:
                continue
            hits, skipped = scan_file(path, root)
            all_hits.extend(hits)
            all_skipped.extend(skipped)
    return all_hits, all_skipped


def write_index(root: Path, hits, skipped):
    hits.sort(key=lambda h: (PRIORITY_RANK.get(h["priority"], 4), h["file"], h["line"]))
    sections = {p: [] for p in ["P0", "P1", "P2", "P3"]}
    for h in hits:
        sections[h["priority"]].append(h)

    out_lines = ["# TODO-INDEX", ""]
    if not hits:
        out_lines.append("_本次扫描无命中_")
    for label, rows in sections.items():
        out_lines.append(f"## {label}")
        out_lines.append("| 文件 | 行号 | 正文 | 类型 | 提出者 |")
        out_lines.append("| --- | --- | --- | --- | --- |")
        for r in rows:
            body = r["body"].replace("|", "\\|")
            out_lines.append(f"| {r['file']} | {r['line']} | {body} | {r['type']} | {r['author']} |")
        out_lines.append("")

    if skipped:
        out_lines.append("---")
        out_lines.append(f"### 跳过文件（{len(skipped)}）")
        out_lines.append("")
        for s in skipped:
            out_lines.append(f"- `{s}`")
        out_lines.append("")

    out_path = root / "TODO-INDEX.md"
    out_path.write_text("\n".join(out_lines), encoding="utf-8")
    return len(hits), len(skipped)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo_root", help="仓库根目录")
    args = ap.parse_args()
    root = Path(args.repo_root).resolve()
    if not root.is_dir():
        sys.stderr.write(f"仓库根目录不存在：{root}\n")
        return 2
    hits, skipped = walk_repo(root)
    count_hits, count_skip = write_index(root, hits, skipped)
    print(f"扫描完成：命中 {count_hits} 条，跳过文件 {count_skip} 个，输出 {root / 'TODO-INDEX.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
