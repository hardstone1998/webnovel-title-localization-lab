# Pilot V0：平台风格候选提示词对比

## 范围与方法

本次对比使用 `data/processed/novel_pairs/pilot_v0/novel_pairs_100.csv` 的前 30 条记录。V2 与 V3 均通过同一 API、同一模型配置、temperature `0.7`、相同八维评分权重和排序逻辑运行；唯一变化是第一阶段提示词版本。每个版本均返回 30/30 成功记录和 360 条候选。

`published_target_title` 只作为离线 Platform Anchor / weak positive 写入评估 CSV，未进入第一阶段生成上下文。它衡量的是平台既有命名的复现/覆盖能力，而不是标题质量的绝对真值。

## 结果

| 指标 | V2 | V3 anchor-first | 变化 |
| --- | ---: | ---: | ---: |
| Top-1 Agreement | 10.0% (3/30) | 6.7% (2/30) | -1 条 |
| Hit@3 | 10.0% (3/30) | 10.0% (3/30) | 0 |
| Hit@Any | 13.3% (4/30) | 16.7% (5/30) | +1 条 |
| 命中时平均排名 | 3.00 | 2.80 | +0.20 名 |
| 候选完整率 | 100.0% | 100.0% | 0 |
| 关键违规候选率 | 3.06% (11/360) | 1.11% (4/360) | -1.94pp |
| 含关键违规的记录率 | 30.0% (9/30) | 10.0% (3/30) | -20pp |

两版的平台标题命中都只来自 `source_title` 策略；V3 在该策略上的 Hit@Any 为 16.7% (5/30)，V2 为 13.3% (4/30)。`synopsis` 和 `market_localized` 在这 30 条中均未精确复现平台标题，这不代表它们没有语义或商业价值，但说明目前的 weak-positive 复现主要依赖原题锚点。

## 决策

V3 满足第一阶段的候选池目标：Hit@Any 增加且关键违规显著下降，候选完整性没有回退。因此保留 V3 为默认提示词版本，并保留 `configs/title_selection.baseline_v0.json` 以复现 V2 基线。

V3 尚未证明 Top-1 提升：样本中少 1 条 Top-1 命中，且 Hit@3 持平。该问题不能归因于候选生成本身；已有平台标题进入候选池后仍可能被第二阶段评分压低。下一步应以独立变更校准评分器或比较偏好排序，不能在 Frozen Test Set 上继续调节第一阶段提示词。

## 制品

- V2 结果：`output/pilot_v0_v2_title_localizations.csv`
- V2 指标：`output/pilot_v0_v2_platform_coverage.json`
- V3 结果：`output/pilot_v0_v3_title_localizations.csv`
- V3 指标：`output/pilot_v0_v3_platform_coverage.json`
