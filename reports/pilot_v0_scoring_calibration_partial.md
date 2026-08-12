# Pilot V0 第二阶段评分校准：定向部分评估

> 状态：部分完成；不得据此切换默认评分配置。  
> 数据范围：`output/pilot_v0_remaining70_title_localizations.csv` 中 69 个完整候选池内，3 个平台标题被精确召回的定向开发案例。  
> 候选池指纹：`c16aef460168449c76a2ea47607fd7ac196d5dec42f3103cd1b12a5c1a3caf63`。  
> 排除：`836baea5014b94c07691c2734c2b123b79620e89` 只有 7 个候选，未进入重评分。  
> 标签边界：平台标题是 Platform Anchor / weak positive，不是标题质量的唯一真值，也未传入模型评分提示词。

## 方法

- 固定每个样本原有的 12 个 `candidate_id`、标题、生成策略与序号；不重新运行第一阶段生成。
- 从对应请求 JSONL 恢复来源简介；V2 和 V3 使用相同候选池、相同八维权重、相同候选排列种子和相同确定性排序规则。
- V3 仅增加“标题不是简介压缩版”的提示词校准规则，并在运行制品中记录 `scoring_prompt_version`。
- 本报告不包含顺序扰动，也不包含独立人工/结构化偏好审阅，因此不能判断 V3 是否提高真实标题质量。

## 结果

| Platform Anchor | V2 排名 / 分数 | V3 排名 / 分数 | 结论 |
| --- | ---: | ---: | --- |
| *Black Tech Internet Cafe System* | 9 / 69.5 | 12 / 61.0 | 回退；V3 未改善该简短标题的相对位置。 |
| *Night Ranger* | 4 / 78.5 | 1 / 88.0 | 提升至 Top 1。 |
| *I Can Track Everything* | 5 / 75.5 | 1 / 81.5 | 提升至 Top 1。 |

三个候选均在 V2/V3 中被精确召回，因此 Hit@Any 均为 1.0。V3 的 Top-1 Agreement 从 0/3 变为 2/3；但样本很小，且 *Black Tech Internet Cafe System* 的明显回退表明该提升不能解释为普适效果。

## 决策

保持 `configs/title_selection.default.json` 的 `eight-dimension-score-v2` 不变。V3 作为 `configs/title_selection.scoring_v3.json` 中的实验性、可复现配置保留。

在完成同一固定候选池的更大规模 V2/V3 对照、候选顺序扰动和独立人工或结构化偏好审阅前，不得将平台标题复现指标单独作为默认配置切换依据。

## 制品

- 每个重评分 CSV 和 manifest 位于 `artifacts/scoring_calibration/`，命名为 `pilot_remaining70_v{2,3}_chunk_<index>`。
- 三个单池对照 JSON：`pilot_remaining70_chunk_{005,013,034}_comparison.json`。
- `scripts/rescore_frozen_candidate_pool.py` 强制保留既有候选池，并记录源 CSV / 请求 JSONL 的 SHA-256、评分版本、分块范围和跳过的不完整池。
