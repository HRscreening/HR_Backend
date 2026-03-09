"""
Post-processor for LLM rubric output.

The LLM is imperfect — this module normalizes, validates, and fixes
common issues in the raw output before it reaches the frontend.

Responsibilities:
  1. Normalize criterion weights to sum exactly 100 per section
  2. Normalize sub-criteria weights to sum exactly 100
  3. Enforce priority uniqueness and sequential ordering
  4. Sort criteria arrays by priority (ascending = most important first)
  5. Normalize empty value to null
  6. Ensure display_name is properly formatted
"""

from configs.log_config import get_logger
import json
import re
from typing import Any, Tuple, List

from src.schemas.rubric_schemas import PipelineRubricOutput

logger = get_logger("rubric_post_processor")


def _snake_to_display(name: str) -> str:
    """Convert snake_case to Title Case."""
    return " ".join(word.capitalize() for word in name.split("_") if word)

def _to_snake(text: str) -> str:
    """
    Best-effort normalization to snake_case for stable rubric keys.
    Keeps only [a-z0-9_] and collapses runs of underscores.
    """
    if text is None:
        return ""
    s = str(text).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def _dedupe_name(name: str, used: set[str]) -> str:
    """Ensure name uniqueness by appending _2, _3, ..."""
    if name not in used:
        used.add(name)
        return name
    i = 2
    while f"{name}_{i}" in used:
        i += 1
    final = f"{name}_{i}"
    used.add(final)
    return final


def _compute_weights_from_importance(items: list[dict], importance_key: str = "importance", max_imp: int = 10) -> list[dict]:
    """
    Compute 'weight' dynamically from 'importance' (1-10 or 1-5).
    Ensures the weights sum to 100.
    """
    if not items:
        return items

    total_imp = sum(item.get(importance_key, (max_imp // 2) or 1) for item in items)
    if total_imp == 0:
        equal_weight = 100 // len(items)
        remainder = 100 - (equal_weight * len(items))
        for i, item in enumerate(items):
            item["weight"] = equal_weight + (1 if i < remainder else 0)
        return items

    factor = 100.0 / total_imp
    new_weights = []
    importances = []
    for item in items:
        imp = item.get(importance_key, (max_imp // 2) or 1)
        importances.append(imp)
        new_weights.append(round(imp * factor))

    diff = 100 - sum(new_weights)
    if diff != 0:
        max_idx = new_weights.index(max(new_weights))
        new_weights[max_idx] += diff

    for i, item in enumerate(items):
        item["weight"] = max(0, new_weights[i])
        item[importance_key] = importances[i]

    return items


def _fix_value_consistency(item: dict) -> dict:
    """Normalize value: empty string or missing → null; ensure value_type is none."""
    val = item.get("value")
    if val is None or (isinstance(val, str) and not val.strip()):
        item["value"] = None
    item["value_type"] = "none"
    return item


def _fix_display_name(item: dict) -> dict:
    """Ensure display_name exists and is properly formatted."""
    if not item.get("display_name"):
        item["display_name"] = _snake_to_display(item.get("name", "unknown"))
    return item


def post_process_rubric(raw_output: dict) -> dict:
    """
    Main entry point. Takes raw LLM output (already parsed to dict)
    and returns a cleaned, validated version.
    """
    try:
        # Domain validation
        if not raw_output.get("domain"):
            raw_output["domain"] = "other"
        if not isinstance(raw_output.get("domain_confidence"), (int, float)):
            raw_output["domain_confidence"] = 0.5

        raw_output["domain_confidence"] = max(0.0, min(1.0, raw_output["domain_confidence"]))

        # Threshold validation
        threshold = raw_output.get("threshold_score", 60)
        raw_output["threshold_score"] = max(0, min(100, int(threshold)))

        # Process each section
        sections = raw_output.get("sections", [])
        if not isinstance(sections, list):
            sections = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            if not section.get("key"):
                section["key"] = "requirements"
            criteria = section.get("criteria", [])
            if not isinstance(criteria, list):
                criteria = []
                section["criteria"] = criteria

            # Fix each criterion
            used_criterion_names: set[str] = set()
            for ci, criterion in enumerate(criteria):
                if not isinstance(criterion, dict):
                    continue

                # Ensure criterion has a stable snake_case name
                if not criterion.get("name"):
                    base = criterion.get("display_name") or criterion.get("label") or f"criterion_{ci + 1}"
                    candidate = _to_snake(base) or f"criterion_{ci + 1}"
                    criterion["name"] = candidate
                criterion["name"] = _dedupe_name(str(criterion["name"]), used_criterion_names)

                _fix_display_name(criterion)
                _fix_value_consistency(criterion)

                # Process sub-criteria
                subs = criterion.get("sub_criteria")
                if subs and isinstance(subs, list) and len(subs) > 0:
                    used_sub_names: set[str] = set()
                    for sub in subs:
                        if not isinstance(sub, dict):
                            continue
                        if not sub.get("name"):
                            base = sub.get("display_name") or f"sub_criterion"
                            candidate = _to_snake(base) or "sub_criterion"
                            sub["name"] = candidate
                        sub["name"] = _dedupe_name(str(sub["name"]), used_sub_names)
                        _fix_display_name(sub)
                        _fix_value_consistency(sub)
                    # Compute weights from importance, then sort by weight desc for stable ordering
                    weighted_subs = _compute_weights_from_importance(subs, "importance", 5)
                    weighted_subs = sorted(
                        weighted_subs,
                        key=lambda sc: (-(sc.get("weight") or 0), -(sc.get("importance") or 0), str(sc.get("name") or "")),
                    )
                    criterion["sub_criteria"] = weighted_subs
                elif subs is not None and (not isinstance(subs, list) or len(subs) == 0):
                    criterion["sub_criteria"] = None

            # Normalize weights across criteria in this section based on importance
            if criteria:
                weighted_criteria = _compute_weights_from_importance(criteria, "importance", 10)
                # Sort by computed weight desc (then importance) so weights are non-increasing by priority
                weighted_criteria = sorted(
                    weighted_criteria,
                    key=lambda c: (-(c.get("weight") or 0), -(c.get("importance") or 0), str(c.get("name") or "")),
                )
                for i, criterion in enumerate(weighted_criteria):
                    criterion["priority"] = i + 1
                section["criteria"] = weighted_criteria

            # Ensure section label exists (default from key: snake_case → Title Case)
            if not section.get("label") and section.get("key"):
                section["label"] = _snake_to_display(section["key"])

        # Ensure at least one section exists
        if not sections:
            sections = [{"key": "requirements", "label": "Requirements", "criteria": []}]

        # Compute section-level weights from section importance
        if len(sections) > 1:
            sections = _compute_weights_from_importance(sections, "importance", 10)
        elif len(sections) == 1:
            sections[0]["weight"] = 100
            sections[0]["importance"] = sections[0].get("importance", 10)

        raw_output["sections"] = sections

        # Completeness check
        warnings = check_rubric_completeness(raw_output)
        if warnings:
            for w in warnings:
                logger.warning("Rubric completeness: %s", w)

        logger.info(
            "Post-processed rubric: domain=%s, sections=%d, total_criteria=%d",
            raw_output.get("domain"),
            len(sections),
            sum(len(s.get("criteria", [])) for s in sections),
        )

        return raw_output

    except Exception as e:
        logger.exception("Post-processing failed, returning raw output: %s", e)
        return raw_output


def is_valid_json(text: str) -> bool:
    """
    Returns True iff `text` is valid JSON (strict).
    This is intended for validating raw LLM output before processing.
    """
    try:
        json.loads(text)
        return True
    except Exception:
        return False


def _safe_numeric(value: Any, kind: str) -> Any:
    """Coerce string/bool to int or float when possible; return as-is otherwise."""
    if kind == "int":
        if type(value) is int:
            return value
        if isinstance(value, (float, str)) and str(value).strip() != "":
            try:
                return int(float(value))
            except (ValueError, TypeError):
                pass
    elif kind == "float":
        if type(value) in (int, float) and type(value) is not bool:
            return float(value)
        if isinstance(value, str) and value.strip() != "":
            try:
                return float(value)
            except (ValueError, TypeError):
                pass
    return value


def validate_rubric_json(payload: Any) -> Tuple[bool, List[str]]:
    """
    Validates that the payload matches the pipeline rubric contract.
    - Payload must be a dict; only rubric structure is validated (no job_data required).
    - Numeric fields are checked (with optional coercion from strings).
    - Weights/priorities are ints in range; section/sub-criteria weights sum to 100.

    Handles any input type: missing keys are reported, wrong types are coerced when safe.
    Returns: (ok, errors)
    """
    errors: list[str] = []

    if payload is None:
        return False, ["payload is required"]
    if not isinstance(payload, dict):
        return False, [f"payload must be a JSON object, got {type(payload).__name__}"]

    # Work with a shallow copy so we can normalize without mutating caller's payload
    payload = dict(payload)

    # --- Type strictness / coercion for top-level numerics ---
    def _is_strict_int(x: Any) -> bool:
        return type(x) is int  # noqa: E721 (intentional: bool must be rejected)

    def _is_strict_number(x: Any) -> bool:
        return type(x) in (int, float) and type(x) is not bool

    dc = payload.get("domain_confidence")
    if dc is not None:
        dc = _safe_numeric(dc, "float")
        payload["domain_confidence"] = dc
        if not _is_strict_number(dc):
            errors.append("domain_confidence must be a number (0.0–1.0), not a string/bool")
    ts = payload.get("threshold_score")
    if ts is not None:
        ts = _safe_numeric(ts, "int")
        payload["threshold_score"] = ts
        if not _is_strict_int(ts):
            errors.append("threshold_score must be an integer (0–100), not a string/bool")

    sections = payload.get("sections")
    if sections is None or not isinstance(sections, list):
        errors.append("sections must be an array")
        sections = []

    for si, section in enumerate(sections):
        if not isinstance(section, dict):
            errors.append(f"sections[{si}] must be an object")
            continue

        criteria = section.get("criteria")
        if criteria is None or not isinstance(criteria, list):
            errors.append(f"sections[{si}].criteria must be an array")
            continue

        # criteria weights monotonicity is a heuristic for JD ordering.
        # We validate non-increasing weights when there are 3+ items.
        weights_seen: list[int] = []

        for ci, c in enumerate(criteria):
            if not isinstance(c, dict):
                errors.append(f"sections[{si}].criteria[{ci}] must be an object")
                continue

            w = c.get("weight")
            p = c.get("priority")
            if not _is_strict_int(w):
                errors.append(f"sections[{si}].criteria[{ci}].weight must be an int")
            elif not (0 <= w <= 100):
                errors.append(f"sections[{si}].criteria[{ci}].weight must be 0..100")
            else:
                weights_seen.append(w)

            if not _is_strict_int(p):
                errors.append(f"sections[{si}].criteria[{ci}].priority must be an int")
            elif p < 1:
                errors.append(f"sections[{si}].criteria[{ci}].priority must be >= 1")

            val = c.get("value")
            if val is not None and not isinstance(val, str):
                errors.append(f"sections[{si}].criteria[{ci}].value must be a string or null")

            subs = c.get("sub_criteria")
            if subs is None:
                continue
            if not isinstance(subs, list):
                errors.append(f"sections[{si}].criteria[{ci}].sub_criteria must be an array or null")
                continue

            sub_weights: list[int] = []
            for sj, sc in enumerate(subs):
                if not isinstance(sc, dict):
                    errors.append(f"sections[{si}].criteria[{ci}].sub_criteria[{sj}] must be an object")
                    continue
                sw = sc.get("weight")
                if not _is_strict_int(sw):
                    errors.append(f"sections[{si}].criteria[{ci}].sub_criteria[{sj}].weight must be an int")
                elif not (0 <= sw <= 100):
                    errors.append(f"sections[{si}].criteria[{ci}].sub_criteria[{sj}].weight must be 0..100")
                else:
                    sub_weights.append(sw)

                sval = sc.get("value")
                if sval is not None and not isinstance(sval, str):
                    errors.append(
                        f"sections[{si}].criteria[{ci}].sub_criteria[{sj}].value must be a string or null"
                    )

            if len(sub_weights) >= 3:
                for a, b in zip(sub_weights, sub_weights[1:]):
                    if a < b:
                        errors.append(
                            f"sections[{si}].criteria[{ci}].sub_criteria weights should be non-increasing by JD order"
                        )
                        break

        if len(weights_seen) >= 3:
            for a, b in zip(weights_seen, weights_seen[1:]):
                if a < b:
                    errors.append(f"sections[{si}].criteria weights should be non-increasing by priority/JD order")
                    break

    # Validate section weights sum to 100 when ≥2 sections exist
    section_weights = [s.get("weight", 0) for s in sections if isinstance(s, dict)]
    if len(section_weights) >= 2:
        total = sum(section_weights)
        if total != 100 and total != 0:
            errors.append(f"Section weights should sum to 100, got {total}")

    # --- Structural validation via pipeline schema (job_data not required) ---
    try:
        PipelineRubricOutput.model_validate(payload)
    except Exception as e:
        errors.append(f"schema validation failed: {e}")

    return (len(errors) == 0), errors


def check_rubric_completeness(rubric: dict) -> List[str]:
    """
    Check that the rubric covers minimum expected dimensions.
    Returns a list of warning strings (empty if complete).
    """
    warnings: List[str] = []

    sections = rubric.get("sections", [])
    if not sections:
        warnings.append("Rubric has no sections")
        return warnings

    all_section_keys = {s.get("key", "") for s in sections if isinstance(s, dict)}
    all_criterion_names = set()
    for s in sections:
        for c in s.get("criteria", []):
            if isinstance(c, dict):
                all_criterion_names.add(c.get("name", "").lower())

    # Check for skills coverage
    skills_keys = {"technical_skills", "core_skills", "required_skills", "skills"}
    has_skills = bool(all_section_keys & skills_keys) or any(
        "skill" in name for name in all_criterion_names
    )
    if not has_skills:
        warnings.append("No skills-related section or criterion found")

    # Check for experience coverage
    experience_keys = {"experience", "work_experience"}
    has_experience = bool(all_section_keys & experience_keys) or any(
        "experience" in name or "years" in name for name in all_criterion_names
    )
    if not has_experience:
        warnings.append("No experience-related section or criterion found")

    # Check total criteria count
    total_criteria = sum(len(s.get("criteria", [])) for s in sections)
    if total_criteria < 2:
        warnings.append(f"Rubric has only {total_criteria} criterion — may be too sparse")

    return warnings
