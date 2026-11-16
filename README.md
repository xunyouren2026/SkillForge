# SkillForge

> **skill-creator** — An AI skill that builds other skills. Give it one sentence of what you need, and it delivers a ready-to-deploy skill package: clear structure, auto-checked quality, and long-term health checks. No dependencies, no secrets — just paste and use.

## 这是什么

**skill-creator** 是一个能让 AI 自己动手做技能的技能。你只要说一句话——比如"帮我把客户反馈整理成表格"——它就会自动帮你把一个完整可用的技能做出来。你不用懂技术细节，它会把该问的问清楚、该写的写完整，最后交给你一个装好就能用的技能包。

## 为什么需要它

很多人都会让 AI 帮忙做技能，但自己做出来的东西常常有三个毛病：

- **写完了平台搜不到它** —— 描述写得不对，用户怎么开口都触发不了
- **真用起来处处漏** —— 步骤缺了、边界没写、失败了不报错而是硬着头皮往下做
- **用久了悄悄失效** —— 交付半年后引用过期了、正文过时了，没人发现

这个项目就是专门治这三个毛病的。

## 它怎么工作

一共六步：判断这个需求值不值得做技能 → 问清需求 → 写好触发描述 → 设计文件结构 → 写正文 → 自动检查并交付。人类只在"确认需求"和"确认交付"两个节点介入。

检查环节是它的核心：十几道自动检查覆盖文件结构、描述规范、用户可能的说法、语义细节，每条判定都带证据可定位。检测器自己还配了"反向夹具"——故意造错的样本必须被报出故障，否则判定就是失灵的。

## 快速开始

在项目根目录下执行（推荐用 `dist/skill-creator`，它经过完整校验）：

```
# 结构校验（11 项）
python dist/skill-creator/scripts/validate_structure.py dist/skill-creator

# 内容合规校验（P001–P012）
python dist/skill-creator/scripts/validate_skill.py dist/skill-creator

# 触发代理测试（含负样本误触发检测）
python dist/skill-creator/scripts/check_triggers.py --skill dist/skill-creator --phrasings tests/phrasings-skill-creator.txt --negatives tests/phrasings-skill-creator-negatives.txt

# 语义项自检（29 项中 14 项自动判定）
python dist/skill-creator/scripts/check_semantics.py dist/skill-creator

# 健康度体检 A3 五项 + 报告生成
python dist/skill-creator/scripts/health_check.py dist/skill-creator --phrasings tests/phrasings-skill-creator.txt --negatives tests/phrasings-skill-creator-negatives.txt --samples tests/produced-skills

# 召回实测回归断言
python tests/recall-test/check_recall.py

# 平台内容审核适配（上传前必跑，红线命中须为 0）
python tests/platform_compat_check.py

# 流水线回归检查（自动优先校验 dist/skill-creator）
python tests/feature_check.py
```

## 目录结构

```
SkillForge/
├── SKILL.md                # 根目录入口（与 skill-creator/SKILL.md 内容一致，便于平台直接识别）
├── skill-creator/          # 成品技能包（源包）
│   ├── SKILL.md            # 六环节流水线主文件（132 行）
│   ├── references/         # 方法文档（核心 7 份 + 扩展 8 份）
│   ├── assets/             # 模板（需求卡、六段骨架、CHANGELOG）
│   └── scripts/            # 校验与体检脚本（结构、内容、触发、语义、体检、用量）
├── dist/skill-creator/     # 干净可分发副本（与源包逐文件哈希一致）
├── skill-creator-guide/    # 项目深度教程（给 AI 读，14 章）
├── docs/                   # 项目说明
├── examples/               # 完整成品范例（供阅读，不进运行时）
├── tests/                  # 回归资产（与技能包平级，不进包）
│   ├── feature_check.py    # 回归检查器（14 段）
│   ├── platform_compat_check.py # 平台内容审核适配检查
│   ├── credibility-report.md # 校验结论（当前有效版本）
│   ├── recall-test/        # 召回实测记录与回归断言
│   ├── semantics-fixtures/ # 语义项自检反向夹具（故意含违规）
│   ├── security-fixtures/  # S009/S010/S011 安全回归夹具
│   └── structure-fixtures/ # 结构与槽位判定夹具
├── LICENSE
├── .gitignore
└── README.md               # 本文件
```

`tests/` 只放**回归资产**（夹具、断言数据、回归脚本），不放过程稿与日期归档报告——中间态（尤其是 FAIL 状态的中间产物）会误导后来的读者。当前结论见 `tests/credibility-report.md`，方法与理由见 `skill-creator-guide/`。

## 安装使用

把 `dist/skill-creator/` 目录复制到你的技能目录即可使用。整个项目仅依赖 Python 标准库，无第三方依赖。

## 许可

MIT，见 [LICENSE](LICENSE)。

## 内容说明

- 主流程：准入判定 → 需求采集 → 触发描述生成 → 结构决策 → 正文生成 → 校验与交付；人类只在需求确认与交付确认两个节点介入。
- 扩展功能（内容合规校验、用量分析、版本与变更记录、增量更新、技能健康度体检、技能组合编排、平台适配、多语言 description、交互式向导、诊断分支）按需加载，见 `skill-creator/SKILL.md` 的「资源索引」与「扩展功能」两节。
- 测试资产全部在 `tests/`，不进技能包。

## 版本与校验状态（v2.2.0）

| 对象 | 结构校验 | 内容校验 | 语义项自检 | 触发测试 | 负样本 | 体检 | 召回实测 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `dist/skill-creator` | 11 PASS | 12 PASS | 14 项自动判定，0 FAIL | 3/3 命中 | 5/5 未误触发 | 健康 | 51/51 判断正确 |
| `skill-creator`（源包） | 11 PASS | 12 PASS | 同上 | 同上 | 同上 | 健康 | 同上 |

## v2.2.0 修复记录

| 项 | 修复前 | 修复后 |
| --- | --- | --- |
| 语义项自检 | 29 项全靠人工判 | 14 项由 `check_semantics.py` 自动判定，剩余 15 项仍人工判 |
| 健康度体检 | 348 行方法论，无脚本 | `health_check.py` 五项体检 + 报告生成，判定健康 / 亚健康 / 不健康 |
| 平台召回 | 只有词面代理指标，未实测 | 真实召回实测：17 条 query × 3 次独立判断，51/51 正确，0 误触发 |
| 召回实测固化 | 无 | `tests/recall-test/check_recall.py` 断言 description 指纹，变更即要求重测 |

## v2.1.1 修复记录

| 项 | 修复前 | 修复后 |
| --- | --- | --- |
| 内容校验 P007 | 子串匹配 `TODO`，误杀 `TODO-INDEX.md` 等合法引用 | 槽位式判定：标记词处于待填写位置才判残留；行内代码与代码块豁免 |
| 结构校验 S004 | `\b(todo\|placeholder\|example)\b` 误伤 `find_todo.py` | 按文件名主干整词判定，`find_todo.py`、`example-config.json` 放行 |
| 触发测试加成 | 固定 +0.35，长触发语 + 短说法虚假满分 | 按触发语覆盖说法的比例给加成 |
| 触发测试盲区 | 只测正样本，无法发现误触发 | 新增 `--negatives` 负样本检测，判据为职责段纯覆盖率 ≥ 0.40 |
| 负样本判据 | 排除句的词会抬高召回得分 | 排除句不计入负样本得分；并配反向夹具验证判据具备检测力 |
| 文档口径 | 正文规格未提醒占位词风险 | body-spec.md 增第 4.1 节槽位残留与合法引用的区分表 |

## 已知限制

1. 平台真实召回的判断由模型自报，不等于平台调度器的实际行为；平台可能用 embedding 相似度而非模型判断，两者会有差异。实测记录与边界见 `tests/recall-test/README.md`。
2. 词面代理测试与真实召回是两套指标：代理测的是结构性漏词，真实召回测的是模型激活行为。两者不能互相替代。
3. 语义项自检覆盖 29 项中的 14 项，剩余 15 项依赖人类确认、跨文件比对或平台外部信息，仍由人工判。
4. 召回实测样本共 17 条，覆盖常见说法形态，无法穷举真实用户表述；新增说法应同步更新 `tests/recall-test/` 并重跑。

