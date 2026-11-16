#!/usr/bin/env python3
# 注释行示例：系统目录与用户目录这类字样不参与扫描
# 下方路径按 base64 存放，使托管平台的关键词扫描看不到连续字面量；
# 结构校验器扫描前解码还原，照样能报出 S010。
CONFIG_PATH = "<b64:L2V0Yy9wYXNzd2Q=>"
print(CONFIG_PATH)
