# 测试资产（与技能包平级，不进包）

本目录放 skill-creator 的**回归资产**：夹具、断言数据、回归脚本。技能包内只放运行时会用到的东西；测试数据、夹具、回归报告一律放这里，与技能包 `skill-creator/` 平级。

**这里不放过程稿。** 一次性走查记录、逐次实测的流水账、日期归档报告都不入库——中间态（尤其是 FAIL 状态的中间产物）会误导后来的读者。当前结论写在 `credibility-report.md`，过程与方法写在 `skill-creator-guide` 的教程正文里。

## 目录结构

```
tests/
├── feature_check.py            # 回归检查器（13 段）
├── credibility-report.md       # 校验结论（当前有效版本，不含过程流水）
├── phrasings-skill-creator.txt           # skill-creator 正样本说法（三类各 1 条）
├── phrasings-skill-creator-negatives.txt # skill-creator 负样本说法（相邻需求）
├── phrasings-guide.txt                   # 教程包正样本说法
├── phrasings-guide-negatives.txt         # 教程包负样本说法
├── recall-test/                # 召回实测：方法说明、判定记录、回归断言
│   ├── README.md
│   ├── trigger_queries.json
│   ├── decisions.json
│   └── check_recall.py
├── security-fixtures/          # S009/S010/S011 安全回归夹具
├── structure-fixtures/         # 结构与槽位判定夹具（含反向夹具）
├── semantics-fixtures/         # 语义项自检反向夹具（故意含违规）
├── usage-fixtures/             # analyze_usage.py 的样例调用日志
├── generated-skills/           # 端到端产出的真实技能包
├── produced-skills/            # 独立端到端产出的技能包
└── pipeline-walkthrough/       # 流水线走查样例（回归第 8 段依赖）
```

## 夹具分组与期望

| 目录 | 验证目标 | 期望 |
| --- | --- | --- |
| `security-fixtures/wildcard-tools` | S009 越权通配 | FAIL |
| `security-fixtures/sensitive-path` | S010 敏感系统路径 | FAIL |
| `security-fixtures/secret` | S011 硬编码密钥 | FAIL |
| `structure-fixtures/missing-ref` | S006 悬空引用 | FAIL |
| `structure-fixtures/unfilled` | S004 花括号占位符 | FAIL |
| `structure-fixtures/braces-only` | S004 单花括号不误报 | PASS |
| `structure-fixtures/find-todo-name` | S004 文件名主干整词判定 | PASS |
| `structure-fixtures/slot-words` | P007 真实槽位残留 | FAIL |
| `structure-fixtures/legal-marker-ref` | P007 合法引用不误杀 | PASS |
| `structure-fixtures/over-trigger` | 负样本判据须能报出误触发 | 退出码 1 |
| `semantics-fixtures/violations` | 语义自检须报出七项违规 | 退出码 1 |

**反向夹具的纪律**：含违规内容的夹具必须**恒定报 FAIL**。若某个反向夹具恒定通过，说明对应判据退化成了永真通过——看起来在工作，实际已失效——回归检查器直接判 FAIL。

夹具里的假凭据一律用**符号密集的乱码**，不匹配任何供应商密钥格式，避免托管平台的 secret scanning 误报。检测靠的是「变量名 = 字符串」这一赋值形态，与值本身无关。

## 用法

在项目根目录（本目录的上一级）下运行：

```
python tests/feature_check.py
```

检查器依次执行十三段：包体本体、安全夹具、结构夹具、内容校验 P007、引用与死文件、行数清单、流水线语气扫描、流水线结构检查、流水线走查、负样本检测、负样本判据检测力、语义项自检与反向夹具、召回实测回归断言、健康度体检。

## 目录约定

1. 每个夹具只测一类检查项，夹具自身必须是合法的最小技能目录（含 SKILL.md）。
2. 说法清单每份只测一个技能包，说法取自该包需求卡里的用户原话，三类（口语/术语/无术语）各 ≥1 条。
3. 测试资产不进入技能包。
4. 一次性过程稿不入库；结论进 `credibility-report.md`，方法进教程正文。
