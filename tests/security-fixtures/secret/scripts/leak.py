#!/usr/bin/env python3
# 注释行示例：赋值形态的假密钥不参与扫描
# 下方值为乱码占位，非真实凭据；用于验证 S011 能报出硬编码密钥。
# 值按 base64 存放，使托管平台的关键词扫描看不到连续字面量；
# 结构校验器扫描前解码还原，照样能报出。
API_KEY = "<b64:Wlo5I3hRIW1MMkB2VzcqYks0JXBS>"
print(len(API_KEY))
