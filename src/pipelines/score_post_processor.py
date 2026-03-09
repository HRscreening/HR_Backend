"""
Score Post-Processor — computes overall_score from per-criterion LLM scores.

Algorithm:
1. For each criterion with sub_criteria:
   criterion_score = weighted_avg(sub_criterion_scores, sub_criterion_weights)
2. For each section:
   section_score = weighted_avg(criterion_scores, effective_criterion_weights)
   where effective_weight = criterion.weight × requirement_level_multiplier
3. overall_score = weighted_avg(section_scores, section_weights)

Requirement level multiplier adjusts the effective weight:
  - must: weight × 1.5
  - should: weight × 1.0
  - nice: weight × 0.5

After multiplying, weights are re-normalized within each section.
"""

from typing import Any
from configs.log_config import get_logger

logger = get_logger("score_post_processor")

REQUIREMENT_MULTIPLIERS = {
    "must": 1.5,
    "should": 1.0,
    "nice": 0.5,
}


def _weighted_avg(values: list[float], weights: list[float]) -> float:
    """Compute weighted average. Falls back to simple average if all weights are zero."""
    if not values:
        return 0.0
    total_weight = sum(weights)
    if total_weight == 0:
        return sum(values) / len(values)
    return sum(v * w for v, w in zip(values, weights)) / total_weight


def compute_weighted_score(
    llm_sections: dict[str, Any],
    rubric_sections: list[dict],
) -> dict:
    """
    Compute the weighted overall score from LLM per-criterion scores and rubric weights.

    Args:
        llm_sections: {section_key: {"criteria": {name: {"score", "reasoning", "sub_criteria"}}}}
        rubric_sections: the rubric sections list with weights and criteria definitions

    Returns:
        {
            "overall_score": float,
            "raw_overall_score": float (before req_level adjustment),
            "section_scores": {section_key: {"score", "raw_score", "criteria_scores": {...}}}
        }
    """
    if not llm_sections:
        logger.error("LLM returned empty sections dict — all scores will be 0")
    if not rubric_sections:
        logger.error("Rubric has no sections — cannot compute scores")

    section_scores = {}
    section_weights = []

    for rubric_section in rubric_sections:
        section_key = rubric_section["key"]
        section_weight = rubric_section.get("weight", 0)
        section_weights.append(section_weight)

        llm_section = llm_sections.get(section_key, {})
        if not llm_section:
            logger.warning(
                "Section %r missing from LLM output. Available LLM keys: %s",
                section_key, list(llm_sections.keys()),
            )
        llm_criteria = llm_section.get("criteria", {}) if isinstance(llm_section, dict) else {}

        criteria_scores = {}
        effective_weights = []
        raw_weights = []

        for criterion in rubric_section.get("criteria", []):
            c_name = criterion["name"]
            c_weight = criterion.get("weight", 0)
            req_level = criterion.get("requirement_level", "should")
            multiplier = REQUIREMENT_MULTIPLIERS.get(req_level, 1.0)

            llm_criterion = llm_criteria.get(c_name, {})
            if not isinstance(llm_criterion, dict):
                llm_criterion = {}
            if not llm_criterion:
                logger.warning(
                    "Criterion %r missing from LLM section %r. LLM criteria keys: %s",
                    c_name, section_key, list(llm_criteria.keys()),
                )
            raw_score = llm_criterion.get("score", 0)
            reasoning = llm_criterion.get("reasoning", "")

            # Compute criterion score from sub-criteria if present
            subs = criterion.get("sub_criteria")
            llm_subs = llm_criterion.get("sub_criteria", {})
            if not isinstance(llm_subs, dict):
                llm_subs = {}

            if subs and len(subs) > 0:
                sub_scores = []
                sub_weights_list = []
                sub_details = {}
                for sub in subs:
                    s_name = sub["name"]
                    s_weight = sub.get("weight", 0)
                    llm_sub = llm_subs.get(s_name, {})
                    if not isinstance(llm_sub, dict):
                        llm_sub = {}
                    s_score = llm_sub.get("score", 0)
                    s_reasoning = llm_sub.get("reasoning", "")
                    sub_scores.append(s_score)
                    sub_weights_list.append(s_weight)
                    sub_details[s_name] = {
                        "score": round(s_score, 2),
                        "reasoning": s_reasoning,
                    }

                criterion_score = _weighted_avg(sub_scores, sub_weights_list)
            else:
                criterion_score = raw_score
                sub_details = {}

            criteria_scores[c_name] = {
                "score": round(criterion_score, 2),
                "raw_llm_score": round(raw_score, 2),
                "reasoning": reasoning,
                "requirement_level": req_level,
                "sub_criteria": sub_details,
            }

            effective_weights.append(c_weight * multiplier)
            raw_weights.append(c_weight)

        # Section score with requirement-level adjustment
        c_scores_list = [
            criteria_scores[c["name"]]["score"]
            for c in rubric_section.get("criteria", [])
            if c["name"] in criteria_scores
        ]
        section_score = _weighted_avg(c_scores_list, effective_weights)
        raw_section_score = _weighted_avg(c_scores_list, raw_weights)

        section_scores[section_key] = {
            "score": round(section_score, 2),
            "raw_score": round(raw_section_score, 2),
            "criteria_scores": criteria_scores,
        }

    # Overall score from section scores
    s_scores = [
        section_scores[s["key"]]["score"]
        for s in rubric_sections
        if s["key"] in section_scores
    ]
    s_raw = [
        section_scores[s["key"]]["raw_score"]
        for s in rubric_sections
        if s["key"] in section_scores
    ]

    overall = _weighted_avg(s_scores, section_weights)
    raw_overall = _weighted_avg(s_raw, section_weights)

    # Diagnostic: warn if overall is suspiciously low
    if overall == 0 and llm_sections:
        logger.error(
            "Overall score is 0 despite LLM returning data. "
            "LLM section keys: %s | Rubric section keys: %s",
            list(llm_sections.keys()),
            [s["key"] for s in rubric_sections],
        )

    logger.info(
        "Weighted score computed: overall=%.2f raw=%.2f sections=%d",
        overall, raw_overall, len(section_scores),
    )

    return {
        "overall_score": round(overall, 2),
        "raw_overall_score": round(raw_overall, 2),
        "section_scores": section_scores,
    }
