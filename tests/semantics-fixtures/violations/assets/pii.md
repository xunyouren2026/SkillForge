# 反向夹具：个人信息类样本

本文件存放一组用于验证检测器的可识别个人信息字段，用于验证语义自检能报出该项。

样本字符串按 base64 存放：

`<b64:6IGU57O75Lq677yaYHpoYW5nc2FuQGV4YW1wbGUuY29tYO+8jOaJi+acuiBgMTM4MDAxMzgwMDBg77yM6Lqr5Lu96K+BIGAxMTAxMDExOTkwMDEwMTEyMzRg>`

托管平台的关键词扫描看到的是一串编码，抓不到红线；
语义自检在扫描前把 base64 载荷解码成原始字符串，照样能抓到。

其中邮箱使用 example.com 保留域名，号码为公开的测试用样例，不对应任何真实个人。
