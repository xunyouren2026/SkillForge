# 示例库

`examples/` 供人阅读，不进入运行时上下文。每个示例展示一个完整成品，或一段真实修复实录；正文与 references 负责方法，这里负责「成品长什么样」。

示例目录本身不参与主流程，读取时机由主文件资源索引给出。

## 1 示例清单

| # | 示例 | 演示什么 | 入口文件 | 结构 |
| --- | --- | --- | --- | --- |
| 1 | 经典力学求解器 | 新建线全流程：需求卡 → description → 目录举证 → 六段正文 → 自检；references/ 与 scripts/ 各一件的举证理由 | `classical-mechanics-solver/SKILL.md` | 5 文件：SKILL.md、README.md、references/ 2 份、scripts/ 1 个 |
| 2 | 线性代数证明助手 | 非显然性判据：模型易用定理证定理，必须先查前置条件；两个 references 分别在不同步骤加载 | `linear-algebra-proof-assistant/SKILL.md` | 4 文件：SKILL.md、README.md、references/ 2 份 |
| 3 | 不触发诊断实录 | 诊断分支 D1–D2：只改 description 的最小修复，两轮后仍未 3/3 的如实记录 | `03-diagnosis-not-triggering.md` | 单篇过程记录，不是技能包 |
| 4 | 客户反馈归类 | 一句话需求到完整包：八字段需求卡、5 条「」原话、六类归类规则、九字段输出 | `customer-feedback-triage/SKILL.md` | 3 文件：SKILL.md、README.md、references/ 1 份 |
| 5 | 周报生成器 | 重复性任务固化：七字段固定输出、事实与计划分开、逐条来源可核对 | `weekly-report-generator/SKILL.md` | 2 文件：SKILL.md、README.md |

## 2 阅读顺序

1. 先看示例 1，对照「目标 → 前置 → 步骤 → 输出示例 → 禁止项 → 常见错误」六段骨架。
2. 再看示例 2，对照目录举证：为什么两个 references 分别只在某一步加载。
3. 接着看示例 3，对照诊断分支：不触发时只动 frontmatter 的最小修复。
4. 最后看示例 4、5，对照一句话需求如何变成可用成品。

## 3 新增示例的准入

1. 完整：从输入到输出可独立跑通，不依赖包外未说明的数据。
2. 无占位符：不出现 `{{...}}`、`TODO`、「示例略」。
3. 真实：示例数据与结果可复现，不编造运行结果。
4. 对应步骤：README 里写明本示例演示 skill-creator 的哪些步骤号。
