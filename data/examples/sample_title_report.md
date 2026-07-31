# 英文剧名生成与评分报告（确定性示例）

- 样本 ID：`synthetic_001`
- 候选数：12
- 策略分布：`source_title=4`、`synopsis=4`、`market_localized=4`
- 评分标准：`title-rubric-v1`
- 结果：`winner_selected`

## 最终剧名：Awakening the God-Tier Sign-In

加权总分：**91.00**

## 完整排名

| 排名 | 英文剧名 | 生成策略 | 加权总分 | 合格 |
| ---: | --- | --- | ---: | :---: |
| 1 | Awakening the God-Tier Sign-In | `source_title` | 91.00 | 是 |
| 2 | The Divine Check-In System | `source_title` | 90.00 | 是 |
| 3 | Every Check-In Makes Me Stronger | `market_localized` | 87.50 | 是 |
| 4 | Check In to Rise Again | `synopsis` | 84.50 | 是 |
| 5 | Leveling Up After the Sect Cast Me Out | `market_localized` | 84.50 | 是 |
| 6 | My Comeback Starts with a Sign-In | `market_localized` | 84.00 | 是 |
| 7 | From Outcast to Overlord | `synopsis` | 82.50 | 是 |
| 8 | Exiled with the Ultimate System | `market_localized` | 79.00 | 是 |
| 9 | The Exile's Hidden System | `synopsis` | 76.00 | 是 |
| 10 | My Supreme Sign-In Power | `source_title` | 75.50 | 是 |
| 11 | Starting with a Divine Check-In | `source_title` | 75.00 | 是 |
| 12 | Banished, Then Blessed | `synopsis` | 74.00 | 是 |

## 胜出者八维得分

| 维度 | 原始分 | 权重 | 加权贡献 |
| --- | ---: | ---: | ---: |
| `semantic_fidelity` | 8 | 20 | 16.00 |
| `natural_english` | 10 | 15 | 15.00 |
| `genre_tone_fit` | 10 | 10 | 10.00 |
| `target_market_fit` | 7 | 10 | 7.00 |
| `reader_appeal` | 10 | 15 | 15.00 |
| `memorability_distinctiveness` | 10 | 10 | 10.00 |
| `clarity_concision` | 8 | 10 | 8.00 |
| `integrity_safety` | 10 | 10 | 10.00 |

- 模型总分：91.00
- 应用程序权威总分：91.00
- 计算不一致：否
- 严重违规：无

该文件由确定性适配器生成，可公开再分发。真实模型结果会随模型、提示词和运行配置变化。
