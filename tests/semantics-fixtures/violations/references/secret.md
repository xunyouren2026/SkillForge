---
name: violations
description: 语义项自检的反向夹具：正文含若干类红线样本，用于验证 check_semantics.py 具备真实判别力。
version: 0.1.0
---
# violations

本夹具故意含违规内容，用于验证语义自检能报出 FAIL。

## 步骤

### S1 采集

- 输入：配置文件
- 动作：读取配置
- 产出：配置副本
- 失败分支：缺失时停下

## 参考

内网地址样例：

`<b64:5YaF572R5Zyw5Z2A5qC35L6L77yaYGh0dHA6Ly8xOTIuMTY4LjEuMTA6ODA4MC9hcGlg77yM6ZyA5oyJIHRva2VuIOiuv+mXruOAgg==>`

该值按 base64 存放，使托管平台的关键词扫描看不到连续字面量，不会被误判为真实内网地址；
语义自检在扫描前把 base64 载荷解码成完整地址，照样能抓到。

此地址为测试构造值，不对应任何真实主机。
