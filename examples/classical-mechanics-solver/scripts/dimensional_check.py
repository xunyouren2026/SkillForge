#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""量纲一致性校验（仅标准库，S4 执行，不读入上下文）。

用 SI 基本量纲向量 (M, L, T) 表示物理量，检查同一方程各项是否量纲一致。
默认演示 classical-mechanics-solver 输出示例中的方程 (1)：
    m·a = m·g·sinθ − μ_k·m·g·cosθ − k·x_s

用法:
    python dimensional_check.py
    python dimensional_check.py --self-test
退出码: 全部一致 -> 0; 存在不一致 -> 1
"""

from __future__ import annotations

import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

Dim = tuple[int, int, int]  # (M, L, T)


def d(m: int = 0, l: int = 0, t: int = 0) -> Dim:
    return (m, l, t)


def multiply(*dims: Dim) -> Dim:
    out = d()
    for x in dims:
        out = (out[0] + x[0], out[1] + x[1], out[2] + x[2])
    return out


def fmt(dim: Dim) -> str:
    label = ("M", "L", "T")
    parts = []
    for name, e in zip(label, dim):
        if e == 0:
            continue
        parts.append(name if e == 1 else f"{name}^{e}")
    return "·".join(parts) if parts else "1（无量纲）"


# SI 基本量纲字典
Q: dict[str, Dim] = {
    "m": d(m=1),                 # kg
    "g": d(l=1, t=-2),           # m/s^2
    "a": d(l=1, t=-2),
    "N": d(m=1, l=1, t=-2),      # 力 N = kg·m/s^2
    "mu": d(),                   # 摩擦系数，无量纲
    "sin": d(), "cos": d(),      # 三角函数，无量纲
    "k": d(m=1, t=-2),           # N/m = kg/s^2
    "x": d(l=1),                 # m
}


def terms_of_motion_equation() -> list[tuple[str, Dim]]:
    """方程 (1) 的四项：m·a / m·g·sinθ / μ_k·m·g·cosθ / k·x_s。"""
    return [
        ("m·a", multiply(Q["m"], Q["a"])),
        ("m·g·sinθ", multiply(Q["m"], Q["g"], Q["sin"])),
        ("μ_k·m·g·cosθ", multiply(Q["mu"], Q["m"], Q["g"], Q["cos"])),
        ("k·x_s", multiply(Q["k"], Q["x"])),
    ]


def check(terms: list[tuple[str, Dim]]) -> tuple[bool, Dim]:
    expected = terms[0][1]
    bad = [(name, dim) for name, dim in terms if dim != expected]
    if bad:
        return False, expected
    return True, expected


def self_test() -> bool:
    """验证量纲运算本身正确，避免校验器给出假阳性。"""
    cases = [
        (multiply(Q["k"], Q["x"]), Q["N"], "k·x 应为力"),
        (multiply(Q["m"], Q["a"]), Q["N"], "m·a 应为力"),
        (multiply(Q["m"], Q["g"]), Q["N"], "m·g 应为力"),
        (multiply(Q["m"], Q["g"], Q["cos"]), Q["N"], "m·g·cosθ 应为力"),
    ]
    ok = True
    for got, want, label in cases:
        passed = got == want
        ok &= passed
        print(f"[{'PASS' if passed else 'FAIL'}] {label}: {fmt(got)}")
    return bool(ok)


def main() -> int:
    ap = argparse.ArgumentParser(description="量纲一致性校验")
    ap.add_argument("--self-test", action="store_true", help="自检量纲运算")
    args = ap.parse_args()

    if args.self_test:
        return 0 if self_test() else 1

    terms = terms_of_motion_equation()
    print("== 运动方程 (1) 量纲校验 ==")
    for name, dim in terms:
        print(f"  {name:<18} → {fmt(dim)}")
    ok, expected = check(terms)
    print(f"期望量纲：{fmt(expected)}")
    print("结论：" + ("PASS — 各项量纲一致" if ok else "FAIL — 存在量纲不一致项"))
    print("提示：量纲一致是必要条件而非充分条件，仍需按 references/checks.md 做极限与符号检查。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
