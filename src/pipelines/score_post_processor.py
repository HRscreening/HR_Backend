"""
Score Post-Processor v2 — flat weighted scoring with 0-10 → 0-100 mapping.

Algorithm:
  LLM returns integer scores 0-10 (anchored scale).
  Display score = raw × 10  (7 → 70).
  overall_score = Σ(display_score × importance) / total_importance

Sections are UI grouping only — they do not contribute to weighting.
Sub-criteria are display-only — they inform the LLM's judgment but are not
averaged into the criterion score.
"""

from typing import Any
from configs.log_config import get_logger

logger = get_logger("score_post_processor")

# Multiplier: LLM returns 0-10, display is 0-100
_SCALE_FACTOR = 10


def compute_flat_score_v2(
    llm_sections: dict[str, Any],
    rubric_sections: list[dict],
) -> dict:
    """
    Flat scoring v2: 0-10 LLM scores mapped to 0-100 for display.

    overall_score = Σ(criterion_score_0_100 × importance) / total_importance

    Args:
        llm_sections: {section_key: {"criteria": {name: {"score": 0-10, ...}}}}
        rubric_sections: rubric sections list with criteria and importance values

    Returns:
        {
            "overall_score": float (0-100),
            "section_scores": { ... },
            "scoring_method": "flat_v2",
        }
    """
    if not llm_sections:
        logger.error("LLM returned empty sections dict — all scores will be 0")
    if not rubric_sections:
        logger.error("Rubric has no sections — cannot compute scores")

    total_importance = sum(
        criterion.get("importance", 5)
        for section in rubric_sections
        for criterion in section.get("criteria", [])
        if criterion.get("name")
    )
    if total_importance == 0:
        total_importance = max(
            sum(len(s.get("criteria", [])) for s in rubric_sections), 1
        )

    section_scores: dict[str, Any] = {}
    weighted_sum = 0.0

    for rubric_section in rubric_sections:
        section_key = rubric_section["key"]
        llm_section = llm_sections.get(section_key, {})
        if not llm_section:
            logger.warning(
                "Section %r missing from LLM output. Available LLM keys: %s",
                section_key, list(llm_sections.keys()),
            )
        llm_criteria = (
            llm_section.get("criteria", {})
            if isinstance(llm_section, dict)
            else {}
        )

        criteria_scores: dict[str, Any] = {}
        section_importance_sum = 0
        section_weighted_sum = 0.0

        for criterion in rubric_section.get("criteria", []):
            c_name = criterion["name"]
            importance = criterion.get("importance", 5)

            llm_criterion = llm_criteria.get(c_name, {})
            if not isinstance(llm_criterion, dict):
                llm_criterion = {}
            if not llm_criterion:
                logger.warning(
                    "Criterion %r missing from LLM section %r. LLM criteria keys: %s",
                    c_name, section_key, list(llm_criteria.keys()),
                )

            # LLM returns 0-10; map to 0-100 for display + scoring
            raw_score = llm_criterion.get("score", 0)
            display_score = round(raw_score * _SCALE_FACTOR, 2)
            reasoning = llm_criterion.get("reasoning", "")

            contribution = round(
                display_score * importance / total_importance, 2
            )

            # Sub-criteria — display only, do NOT affect criterion score
            subs = criterion.get("sub_criteria")
            llm_subs = llm_criterion.get("sub_criteria", {})
            if not isinstance(llm_subs, dict):
                llm_subs = {}

            sub_display: dict[str, Any] = {}
            if subs:
                for sub in subs:
                    s_name = sub["name"]
                    llm_sub = llm_subs.get(s_name, {})
                    if not isinstance(llm_sub, dict):
                        llm_sub = {}
                    sub_raw = llm_sub.get("score", 0)
                    sub_display[s_name] = {
                        "score": round(sub_raw * _SCALE_FACTOR, 2),
                        "raw_llm_score": sub_raw,
                        "reasoning": llm_sub.get("reasoning", ""),
                    }

            criteria_scores[c_name] = {
                "score": display_score,
                "raw_llm_score": raw_score,
                "reasoning": reasoning,
                "importance": importance,
                "contribution": contribution,
                "sub_criteria": sub_display,
            }

            weighted_sum += display_score * importance
            section_importance_sum += importance
            section_weighted_sum += display_score * importance

        section_display_score = (
            section_weighted_sum / section_importance_sum
            if section_importance_sum > 0
            else 0.0
        )

        section_scores[section_key] = {
            "score": round(section_display_score, 2),
            "criteria_scores": criteria_scores,
        }

    overall = weighted_sum / total_importance if total_importance > 0 else 0.0

    if overall == 0 and llm_sections:
        logger.error(
            "Overall score is 0 despite LLM returning data. "
            "LLM section keys: %s | Rubric section keys: %s",
            list(llm_sections.keys()),
            [s["key"] for s in rubric_sections],
        )

    logger.info(
        "Flat score v2 computed: overall=%.2f sections=%d",
        overall, len(section_scores),
    )

    return {
        "overall_score": round(overall, 2),
        "section_scores": section_scores,
        "scoring_method": "flat_v2",
    }
