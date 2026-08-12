# Pilot V0 第二阶段评分校准：69 个完整池全量评估

> 决策：保持 `configs/title_selection.default.json` 的 V2 默认评分提示词不变；V3 保留为实验性配置。  
> 范围：冻结的 Pilot / 开发数据中 69 个完整候选池，每池 12 个候选（共 828 个候选）。未重新生成候选，也未混入 Frozen Test Set。  
> 排除：`836baea5014b94c07691c2734c2b123b79620e89` 仅有 7 个候选，未进入对照。  
> 标签边界：平台剧名只作 Platform Anchor / weak positive；未传入 V2、V3 或盲审提示词，且不是标题质量的唯一真值。

## 可复现输入

- 冻结候选池：`output/pilot_v0_remaining70_title_localizations.csv`
  - SHA-256：`c16aef460168449c76a2ea47607fd7ac196d5dec42f3103cd1b12a5c1a3caf63`
- 请求输入（仅用于恢复来源简介）：`output/pilot_v0_remaining70_request_inputs.jsonl`
  - SHA-256：`80249931959fad4b2418e08610385f41ea1316ccb90c810f17b9a55e6dcef91d`
- 基线：`eight-dimension-score-v2`
- 校准版：`eight-dimension-score-v3-title-granularity`
- 保持不变：候选池、八维权重、候选策略、关键违规处理、确定性 tie-break 规则。

## 全量 V2 / V3 对照

| 指标 | V2 | V3 | 变化 |
| --- | ---: | ---: | ---: |
| 完整候选池 | 69 / 69 | 69 / 69 | — |
| 候选完整率 | 100% | 100% | — |
| Platform Anchor Top-1 Agreement | 1 / 69（1.45%） | 3 / 69（4.35%） | +2 |
| Hit@3 | 3 / 69（4.35%） | 5 / 69（7.25%） | +2 |
| Hit@Any | 9 / 69（13.04%） | 9 / 69（13.04%） | 0 |
| 命中时平均排名 | 6.0 | 5.0 | +1.0 名 |
| 含 critical 候选 | 11 / 828（1.33%） | 13 / 828（1.57%） | +2 候选 |
| 含 critical 的记录 | 6 / 69（8.70%） | 4 / 69（5.80%） | -2 记录 |

V3 对平台锚点的弱正向指标有所改善，但平台剧名不是唯一真值；同时 critical 指标呈混合信号，不能单独支持默认切换。

V3 相对 V2 的平均维度分数变化：`semantic_fidelity +0.261`、`natural_english +0.098`、`genre_tone_fit +0.207`、`target_market_fit +0.383`、`reader_appeal +0.297`、`memorability_distinctiveness +0.502`、`clarity_concision +0.162`、`integrity_safety +0.051`。V3 更倾向奖励市场标题功能与辨识度，但仅凭分数上升不能证明排序更可靠。

两版 Top-1 在 48 / 69 个池中改变（69.57%），因此它是实质性评分行为变化，而不是微小校准。

## 顺序扰动

对同一 69 个冻结候选池，V3 分别以三个候选排列种子（`20260801`、`20260802`、`20260803`）重跑：

| 指标 | 结果 |
| --- | ---: |
| 三次均相同 Top-1 的池 | 11 / 69 |
| Top-1 稳定率 | **15.94%** |
| 至少一次 Top-1 改变的池 | 58 / 69（84.06%） |

此稳定率远低于可作为默认排序器的要求。V3 当前对候选呈现顺序高度敏感，故不能切换为默认。

## 盲化结构化偏好审阅

仅审阅 V2/V3 Top-1 不同的 48 个池。每个池将两种赢家确定性地打乱为 A/B；审阅提示词只看到来源上下文与 A/B 标题，**不含**平台剧名、评分分数、V2/V3 身份。每条结果以 JSONL checkpoint 留存。

| 结果 | 样本数 |
| --- | ---: |
| 偏好 V3 | 28 / 48 |
| 偏好 V2 | 19 / 48 |
| 平局 | 1 / 48 |
| 高 / 中 / 低置信度 | 26 / 21 / 1 |

盲审显示 V3 赢标题在这批“有分歧”的样本上存在质量吸引力。然而审阅使用的是已配置的同类模型，并非与评分器独立的人工评审；因此它是结构化辅助证据，不能抵消顺序扰动暴露的稳定性风险。

## 质量护栏与决定

1. 无标签泄漏：满足。平台剧名未进入评分和盲审提示词。
2. 结构化偏好：V3 不回退（28:19，另有 1 个平局），但不是独立人工证据。
3. 排序稳定性：**不满足**。三次顺序扰动只有 15.94% 的冠军稳定。

因此：**不切换默认 V2**。继续保留 `configs/title_selection.scoring_v3.json`，后续应先降低 V3 的顺序敏感性（例如固定候选的独立逐项评分或更强的成对比较约束），再在同一冻结开发池复验稳定性，并补充独立人工审阅后再考虑默认切换。

## 制品

- 全量结果：`artifacts/scoring_calibration/pilot_remaining70_v2_full.csv`、`artifacts/scoring_calibration/pilot_remaining70_v3_full.csv`
- 全量对照：`artifacts/scoring_calibration/pilot_remaining70_v2_v3_full_comparison.json`
- 覆盖和违规统计：`pilot_remaining70_v{2,3}_full_coverage.json`
- 顺序扰动与稳定性：`pilot_remaining70_v3_perm_{101,102,103}_full.csv`、`pilot_remaining70_v3_order_stability.json`
- 盲审输入、逐条结果与汇总：`pilot_remaining70_v2_v3_structured_review.csv`、`pilot_remaining70_v2_v3_structured_review_results.jsonl`、`pilot_remaining70_v2_v3_structured_review_summary.json`
