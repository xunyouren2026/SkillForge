---
name: legal-marker-ref
description: 合法引用夹具：正文含 TODO-INDEX.md、说明句中的 TODO 关键字、代码块内的 TODO 标记，均属合法引用，P007 不应报 FAIL。
version: 0.1.0
---
# legal-marker-ref

产出文件名为 TODO-INDEX.md。

扫描时按 TODO 关键字匹配，命中后写入索引。

示例输出：

```
# TODO-INDEX
| 文件 | 正文 |
| src/a.py | TODO: 待补 |
```
