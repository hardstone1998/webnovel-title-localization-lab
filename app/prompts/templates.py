"""Prompt templates for candidate generation and scoring.

All LLM prompts are centralized here so they can be reviewed and tuned
without touching pipeline logic. Each template uses Python format-string
placeholders — call the ``build_*`` functions to inject runtime data.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Generation prompts
# ---------------------------------------------------------------------------

_STRATEGY_INSTRUCTIONS: dict[str, str] = {
    "source_title": "仅改编中文原始剧名的核心概念，不得从故事简介虚构卖点。",
    "synopsis": "根据故事简介中的前提、冲突、主角或卖点创作英文剧名。",
    "market_localized": "结合全部上下文，创作符合目标英语市场习惯的本土化剧名。",
}

GENERATION_PROMPT_TEMPLATE = """\
生成 {count} 个互不重复、非空且自然的英文剧名。{strategy_instruction}
上下文：{context}
不得使用：{excluded_titles}
只返回 JSON：{{"titles":["..."]}}。不得评分或选择胜出者。"""


def build_generation_prompt(
    strategy: str,
    count: int,
    context: dict[str, Any],
    excluded_titles: tuple[str, ...] = (),
) -> str:
    """Format the generation prompt for a given strategy.

    Parameters
    ----------
    strategy:
        One of ``source_title``, ``synopsis``, ``market_localized``.
    count:
        Number of titles to request.
    context:
        Serialized context dict (already JSON-encoded by the caller).
    excluded_titles:
        Tuple of titles that must not be reused.
    """
    import json

    strategy_instruction = _STRATEGY_INSTRUCTIONS[strategy]
    return GENERATION_PROMPT_TEMPLATE.format(
        count=count,
        strategy_instruction=strategy_instruction,
        context=json.dumps(context, ensure_ascii=False, sort_keys=True),
        excluded_titles=json.dumps(excluded_titles, ensure_ascii=False),
    )


# ---------------------------------------------------------------------------
# Scoring prompts
# ---------------------------------------------------------------------------

SCORING_PROMPT_TEMPLATE = """\
你是英文剧名评审。独立评估全部候选，不得增加、删除、改写剧名，也不得推断生成策略。
源内容：{source_context}
评分标准：{rubric}
候选：{candidates}
每个候选必须给出八项整数得分、简短理由、按权重计算的贡献和总分。同时标记错误代码及 critical/major/minor/note 严重度。其中 SEMANTIC_MISMATCH、ENTITY_ERROR、GENRE_MISMATCH、HOOK_INVENTED 可构成严重违规。只返回结构化 JSON。
JSON 格式：{{"scores":[{{"candidate_id":"...","title":"...","dimensions":{{"dimension_name":{{"score":int,"rationale":"...","weighted_contribution":number}}}},"violations":[{{"code":"...","severity":"...","rationale":"...","evidence_field":"..."}}],"weighted_total":number}}]}}"""


def build_scoring_prompt(
    source_context: dict[str, Any],
    rubric: dict[str, Any],
    candidates: list[dict[str, str]],
) -> str:
    """Format the scoring prompt.

    Parameters
    ----------
    source_context:
        Source title, synopsis, genre, languages, etc.
    rubric:
        Per-dimension weight + guidance + scale.
    candidates:
        List of ``{"candidate_id": ..., "title": ...}`` dicts.
    candidates:
        List of ``{{"candidate_id": ..., "title": ...}}`` dicts.
    """
    import json

    return SCORING_PROMPT_TEMPLATE.format(
        source_context=json.dumps(source_context, ensure_ascii=False, sort_keys=True),
        rubric=json.dumps(rubric, ensure_ascii=False, sort_keys=True),
        candidates=json.dumps(candidates, ensure_ascii=False),
    )
