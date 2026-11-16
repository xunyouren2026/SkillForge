#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调用日志用量分析器（只读，仅标准库，Python 3.8+）。

用法:
    python scripts/analyze_usage.py --log <日志文件> [--json] [--skill <名称>]

日志为 JSONL，每行一个 JSON 对象，字段约定：
    ts      调用时间字符串，取前 10 位作为日期，建议 ISO 8601
    skill   技能名，非空字符串
    query   用户说法，字符串
    invoked 是否被触发，布尔值
    success 本次调用是否成功，布尔值
    turns   轮次数，非负整数
    error   失败原因，字符串或 null，可为空
输出指标：总调用数、按 skill 分组、触发命中率、成功率、平均轮次、
失败原因 Top3、按日期趋势。只读日志，不修改任何文件。
--skill 过滤后无匹配记录时输出零值并返回 0；整份日志为空返回 1。退出码: 0 正常；1 日志格式错误或日志为空；2 参数错误或文件不可读。
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

FIELDS = ("ts", "skill", "query", "invoked", "success", "turns")
TYPES = {"ts": str, "skill": str, "query": str, "invoked": bool, "success": bool, "turns": int}
NO_REASON = "未填写失败原因"

class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "参数错误：%s\n" % message)

def check_record(item):
    for field in FIELDS:
        if field not in item:
            return "缺少字段 %s" % field
    for field, kind in TYPES.items():
        if not isinstance(item[field], kind) or (kind is int and isinstance(item[field], bool)):
            name = "非负整数" if kind is int else ("布尔值" if kind is bool else "字符串")
            return "字段 %s 类型错误，应为%s" % (field, name)
    if not item["ts"].strip() or not item["skill"].strip():
        return "字段 ts 与 skill 不能为空"
    if item["turns"] < 0:
        return "字段 turns 必须为非负整数"
    error = item.get("error")
    if error is not None and not isinstance(error, str):
        return "字段 error 必须为字符串或 null"
    item["error"] = (error or "").strip()
    return None

def load_records(path):
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return None, "日志文件不是 UTF-8 编码，转换后重试"
    except OSError as exc:
        return None, "日志文件不可读：%s" % exc
    records = []
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            return None, "第 %d 行 JSON 解析失败：%s" % (no, exc)
        if not isinstance(item, dict):
            return None, "第 %d 行不是 JSON 对象" % no
        problem = check_record(item)
        if problem:
            return None, "第 %d 行%s" % (no, problem)
        records.append(item)
    return records, None

def summarize(records):
    total = len(records)
    invoked = sum(1 for r in records if r["invoked"])
    success = sum(1 for r in records if r["success"])
    turns = sum(r["turns"] for r in records)
    return {"total": total, "invoked": invoked, "success": success,
            "hit_rate": round(invoked / total, 4) if total else 0.0,
            "success_rate": round(success / total, 4) if total else 0.0,
            "failures": total - success,
            "avg_turns": round(turns / total, 2) if total else 0.0}

def build_report(records, skill):
    groups = {}
    for r in records:
        groups.setdefault(r["skill"], []).append(r)
    by_skill = [dict(skill=name, **summarize(items))
                for name, items in sorted(groups.items())]
    counts = Counter(r["error"] or NO_REASON for r in records if not r["success"])
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    buckets = {}
    for r in records:
        day = r["ts"][:10] if len(r["ts"]) >= 10 and r["ts"][4] == "-" and r["ts"][7] == "-" else "未知日期"
        total, invoked = buckets.get(day, (0, 0))
        buckets[day] = (total + 1, invoked + int(r["invoked"]))
    return {"filter": {"skill": skill or None},
            "summary": summarize(records),
            "by_skill": by_skill,
            "failure_top3": [{"reason": k, "count": v} for k, v in ranked[:3]],
            "trend": [{"date": d, "total": t, "invoked": i}
                      for d, (t, i) in sorted(buckets.items())]}

def print_text(report, log_name):
    s = report["summary"]
    skill = report["filter"]["skill"]
    print("== 用量分析：%s ==\n筛选：%s"
          % (log_name, "skill=%s" % skill if skill else "全部记录"))
    print("总调用数：%d；触发命中：%d / %d = %.1f%%；成功：%d / %d = %.1f%%；平均轮次：%.2f"
          % (s["total"], s["invoked"], s["total"], s["hit_rate"] * 100,
             s["success"], s["total"], s["success_rate"] * 100, s["avg_turns"]))
    print("-" * 66)
    print("%-18s%6s%6s%9s%6s%9s%8s" % ("skill", "调用", "命中", "命中率", "成功", "成功率", "平均轮次"))
    for row in report["by_skill"]:
        print("%-18s%6d%6d%8.1f%%%6d%8.1f%%%8.2f"
              % (row["skill"], row["total"], row["invoked"], row["hit_rate"] * 100,
                 row["success"], row["success_rate"] * 100, row["avg_turns"]))
    print("失败原因 Top3：" + ("无失败记录" if not report["failure_top3"] else ""))
    for i, item in enumerate(report["failure_top3"], 1):
        print("  %d. %s（%d 次）" % (i, item["reason"], item["count"]))
    print("-" * 66 + "\n按日期趋势：")
    for item in report["trend"]:
        print("  %s  调用 %d 条，命中 %d 条" % (item["date"], item["total"], item["invoked"]))

def main():
    parser = Parser(description="调用日志用量分析（只读，JSONL 输入）")
    parser.add_argument("--log", help="日志文件路径，JSONL 格式")
    parser.add_argument("--skill", help="仅统计指定 skill 的记录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式结果")
    args = parser.parse_args()
    if not args.log:
        print("参数错误：缺少必填参数 --log", file=sys.stderr); return 2
    log_path = Path(args.log)
    if not log_path.is_file():
        print("文件错误：日志文件不存在或不是普通文件：%s" % log_path, file=sys.stderr); return 2
    records, problem = load_records(log_path)
    if problem:
        print("日志错误：%s" % problem, file=sys.stderr); return 1
    if not records:
        print("日志错误：未读到任何记录，文件为空或只有空行", file=sys.stderr); return 1
    if args.skill:
        records = [r for r in records if r["skill"] == args.skill]
    report = build_report(records, args.skill)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report, log_path.name)
    return 0

if __name__ == "__main__":
    sys.exit(main())
