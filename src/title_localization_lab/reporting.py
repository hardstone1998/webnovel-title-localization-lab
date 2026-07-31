"""Human-readable reporting over completed artifacts."""

from __future__ import annotations

from .contracts import CandidateSet, RankingResult


def render_markdown_report(
    candidate_set: CandidateSet,
    ranking: RankingResult,
) -> str:
    candidate_by_id = {item.candidate_id: item for item in candidate_set.candidates}
    score_by_id = {item.candidate_id: item for item in ranking.scores}
    lines = [
        "# 英文剧名生成与评分报告",
        "",
        f"- 样本 ID：`{ranking.sample_id}`",
        f"- 候选集：`{ranking.candidate_set_id}`",
        f"- 评分标准：`{ranking.rubric_version}`",
        f"- 权重版本：`{ranking.weight_version}`",
        f"- 结果：`{ranking.outcome}`",
        "",
    ]
    if ranking.winner_candidate_id:
        winner = candidate_by_id[ranking.winner_candidate_id]
        winner_score = score_by_id[ranking.winner_candidate_id]
        lines.extend(
            [
                f"## 最终剧名：{winner.title}",
                "",
                f"加权总分：**{winner_score.authoritative_total}**",
                "",
            ]
        )
    else:
        lines.extend(["## 没有合格胜出者", "", ranking.no_winner_reason or "", ""])

    lines.extend(
        [
            "## 完整排名",
            "",
            "| 排名 | 英文剧名 | 生成策略 | 加权总分 | 合格 |",
            "| ---: | --- | --- | ---: | :---: |",
        ]
    )
    for rank, candidate_id in enumerate(ranking.ordered_candidate_ids, start=1):
        candidate = candidate_by_id[candidate_id]
        score = score_by_id[candidate_id]
        lines.append(
            f"| {rank} | {candidate.title} | `{candidate.strategy}` | "
            f"{score.authoritative_total} | {'是' if score.eligible else '否'} |"
        )

    lines.extend(["", "## 八维得分", ""])
    for candidate_id in ranking.ordered_candidate_ids:
        candidate = candidate_by_id[candidate_id]
        score = score_by_id[candidate_id]
        lines.extend(
            [
                f"### {candidate.title}",
                "",
                "| 维度 | 原始分 | 权重 | 加权贡献 |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for dimension, detail in score.dimensions.items():
            lines.append(
                f"| `{dimension}` | {detail.score} | "
                f"{ranking.weights[dimension]} | {detail.authoritative_contribution} |"
            )
        lines.extend(
            [
                "",
                f"- 模型总分：{score.model_total}",
                f"- 权威总分：{score.authoritative_total}",
                f"- 计算不一致：{'是' if score.arithmetic_mismatch else '否'}",
                f"- 严重违规：{'；'.join(item.code for item in score.violations) or '无'}",
                "",
            ]
        )
    return "\n".join(lines)
