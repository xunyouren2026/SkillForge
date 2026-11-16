# 校验结论

本文件记录 skill-creator 的校验结论与依据。**不记录逐次实测的过程流水**——过程稿是一次性的，中间态（尤其是 FAIL 状态的中间产物）会误导后来的读者；本文件只保留当前有效的结论。

每条结论必须能被重新执行验证。命令与判据写在 `skill-creator-guide` 的教程正文里，以及各校验脚本的 docstring 里。

## 1 当前校验状态

对 `dist/skill-creator`（分发副本）实测：

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 结构校验 | `validate_structure.py dist/skill-creator` | 11 PASS / 0 WARN / 0 FAIL |
| 内容校验 | `validate_skill.py dist/skill-creator` | 12 PASS / 0 WARN / 0 FAIL |
| 语义项自检 | `check_semantics.py dist/skill-creator` | 14 项自动判定 / 0 FAIL / 3 WARN |
| 触发测试 | `check_triggers.py --skill dist/skill-creator --phrasings ... --negatives ...` | 3/3 命中；负样本 5/5 未误触发 |
| 召回实测 | `recall-test/check_recall.py` | 51/51 判断正确，0 误触发，0 抖动 |
| 健康度体检 | `health_check.py dist/skill-creator ...` | 健康（5 项全 PASS） |

回归检查器 `feature_check.py` 十三段全部通过，退出码 0。

`dist/skill-creator` 与 `skill-creator/` 逐文件哈希一致。

### 三条 WARN 的说明

语义项自检的 3 个 WARN 是**需人工确认**的合理状态，不是缺陷：

| 项 | WARN 原因 |
| --- | --- |
| 第 8 项 | skill-creator 主文件是流水线规范，不是产出型技能正文，无 S1…Sn 步骤结构 |
| 第 10 项 | 同上，无「输出示例」段的产出型结构 |
| 第 16 项 | 许可与版权的来源清单无法由脚本判定，需人工确认 |

## 2 触发面结论

| 判据 | 数值 | 说明 |
| --- | --- | --- |
| 命中阈值 | ≥0.30 | 字符二元组重合度 |
| 边缘阈值 | 0.18–0.30 | 观察项，不阻塞 |
| 显式触发语加成 | ≤0.35 | 按触发语覆盖说法的比例给，非固定值 |
| 负样本混淆阈值 | 0.40 | 职责段纯覆盖率 |

负样本得分只在 description 的**职责段**（做什么 + 什么时候用）上计算，排除句不计入——排除句里的词是用来排斥的，用它算召回方向相反。

## 3 召回实测结论

| 项 | 数值 |
| --- | --- |
| query 总数 | 17 |
| 正样本 / 负样本 | 6 / 11 |
| 独立判断次数 | 51（每条 3 次） |
| 判定正确 | 51/51 |
| 误触发 / 漏触发 / 抖动 | 0 / 0 / 0 |

方法与边界见 `recall-test/README.md`。

## 4 已修复的判据缺陷

以下缺陷曾导致误判或漏判，均已修复并配了夹具防止回归。每条的反向夹具必须报出 FAIL，若恒定通过则回归判 FAIL。

| 缺陷 | 症状 | 修法 | 防回归资产 |
| --- | --- | --- | --- |
| P007 朴素子串匹配 | `TODO-INDEX.md` 等合法引用被判残留 | 槽位式判定，判语法位置 | `structure-fixtures/slot-words`、`legal-marker-ref` |
| P007 通用槽位词子串匹配 | 「尚待填写完整」被判残留 | 按末尾不接汉字判定 | 同上 |
| S004 文件名正则匹配 | `find_todo.py` 被判占位文件 | 按文件名主干整词判定 | `structure-fixtures/find-todo-name` |
| 触发加成固定值 | 长触发语配短说法虚假满分 | 按覆盖比例给加成 | `tests/phrasings-skill-creator.txt` |
| 无负样本检测 | 无法发现误触发 | 新增 `--negatives` | `tests/phrasings-skill-creator-negatives.txt` |
| 负样本用正样本最低分为基线 | 基线恒为 1.0，判据退化为永真通过 | 固定阈值比较纯覆盖率 | `structure-fixtures/over-trigger` |
| 排除句参与召回计算 | 「不覆盖账号授权」把「登录账号」抬成误触发 | 截断排除句，只算职责段 | 同上 |
| 检查器扫自身源码 | 检测器被判含敏感路径 / 引子进程 | 排除自身 + 字面量分段拼接 + 合法用法不判违规 | `tests/feature_check.py` 第 2、11 段 |
| 否定语境误伤 | 「不绕过鉴权」被判敏感内容 | 行级否定标记豁免 | `semantics-fixtures/violations` |
| 写盘路径越界漏判 | 路径写在变量里则漏 | 模块级常量追踪 | 同上 |
| 硬编码行号断言 | 夹具一改行断言即失效 | 动态求出违规行号 | `tests/feature_check.py` 第 2 段 |
| 平台审核红线字面量 | 上传被判「审核不通过」 | 红线字符串按拼接存放 + 检测器扫描前还原 + 适配检查入回归 | `tests/platform_compat_check.py` |

## 5 已知边界

这些不是待修的缺陷，是方法本身的边界，写在这里避免被误当成已解决。

1. **真实召回的判断由模型自报**，不等于平台调度器的实际行为；平台可能用 embedding 相似度而非模型判断。
2. **词面代理测试与真实召回是两套指标**，前者测结构性漏词，后者测模型激活行为，不能互相替代。
3. **语义项自检覆盖 29 项中的 14 项**，剩余 15 项依赖人类确认、跨文件比对或平台外部信息。
4. **召回实测样本 17 条**，覆盖常见说法形态，无法穷举真实用户表述。
5. **体检脚本编排其他脚本时用 subprocess**，这是合法用法；第 28 项因此不把 import subprocess 判为违规。
6. **业务内容正确性不由脚本判定**，四套校验全过只说明形态与表述合规。

## 6 复现方式

```
python tests/feature_check.py
```

一条命令跑完上述全部检查，退出码 0 表示全部通过。
