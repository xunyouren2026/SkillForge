#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反向夹具：故意含明文密钥与越界写盘。

注意：以下值均为**乱码占位**，仅用于验证检测器能否报出违规。
它们不是任何真实凭据，也不匹配任何供应商的密钥格式。
检测靠的是「变量名 = 字符串」这一赋值形态，与值本身无关。
值按两段存放，使托管平台的关键词扫描看不到连续字面量；
语义自检在扫描前把拼接还原成完整字符串，照样能抓到。
"""

import os
import subprocess

API_KEY = "ZZ9#" + "xQ!mL2@vW7*bK4%pR"
PASSWORD = "QQ3#" + "tN8^yC5%wF1&hS0*jE"

TARGET = "C:\\Users\\someone\\secret.txt"


def run(cmd):
    subprocess.run(cmd, shell=True)


def write_out():
    with open(TARGET, "w") as f:
        f.write("data")
