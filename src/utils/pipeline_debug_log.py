"""
Pipeline debug logger — writes human-readable results to logs/pipeline_debug.log

Captures:
  - PDF text extraction results
  - Candidate info extraction (name, email, phone)
  - LLM scoring output (section keys, raw scores)
  - Post-processed final scores

Usage:
    from src.utils.pipeline_debug_log import pdlog
    pdlog.extraction(file_name, parsed_text, method)
    pdlog.candidate_info(resume_id, ci)
    pdlog.scoring_llm_output(resume_id, llm_result, rubric_section_keys)
    pdlog.scoring_final(resume_id, overall_score, section_scores)
"""

import os
from datetime import datetime

_LOG_PATH = os.path.join(
    os.path.dirname(__file__),   # src/utils/
    "..", "..",                  # HR_Backend/
    "logs", "pipeline_debug.log"
)
_LOG_PATH = os.path.abspath(_LOG_PATH)


def _write(lines: list[str]):
    os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _sep(char="─", width=70) -> str:
    return char * width


class PipelineDebugLog:

    def extraction(self, file_name: str, parsed_text: str, method: str, page_count: int = 0):
        """Log PDF/DOCX text extraction result."""
        preview = (parsed_text or "")[:500].replace("\n", " ")
        lines = [
            _sep("═"),
            f"[{_ts()}] EXTRACTION  file={file_name}",
            f"  method       : {method}",
            f"  pages        : {page_count}",
            f"  text_length  : {len(parsed_text or '')} chars",
            f"  text_preview : {preview!r}",
            _sep(),
        ]
        _write(lines)

    def candidate_info(
        self,
        resume_id: str,
        full_name,
        email,
        phone,
        source: str = "llm",
    ):
        """Log extracted candidate info."""
        lines = [
            f"[{_ts()}] CANDIDATE_INFO  resume_id={resume_id}  source={source}",
            f"  full_name : {full_name!r}",
            f"  email     : {email!r}",
            f"  phone     : {phone!r}",
        ]
        _write(lines)

    def scoring_llm_output(
        self,
        resume_id: str,
        llm_section_keys: list[str],
        rubric_section_keys: list[str],
        section_criterion_scores: dict,  # {section_key: {criterion_name: score}}
    ):
        """Log what the LLM returned for scoring — section keys and per-criterion scores."""
        lines = [
            _sep("─"),
            f"[{_ts()}] SCORING_LLM  resume_id={resume_id}",
            f"  rubric_keys : {rubric_section_keys}",
            f"  llm_keys    : {llm_section_keys}",
            f"  keys_match  : {sorted(llm_section_keys) == sorted(rubric_section_keys)}",
        ]
        for section_key, criteria in section_criterion_scores.items():
            lines.append(f"  [{section_key}]")
            for c_name, score in criteria.items():
                lines.append(f"    {c_name}: {score}")
        _write(lines)

    def scoring_final(
        self,
        resume_id: str,
        overall_score: float,
        section_scores: dict,  # {section_key: {"score": float, "criteria_scores": {...}}}
    ):
        """Log the post-processed final weighted scores."""
        lines = [
            f"[{_ts()}] SCORING_FINAL  resume_id={resume_id}",
            f"  overall_score : {overall_score}",
        ]
        for section_key, section_data in section_scores.items():
            s_score = section_data.get("score", 0)
            lines.append(f"  [{section_key}]  score={s_score}")
            for c_name, c_data in section_data.get("criteria_scores", {}).items():
                lines.append(f"    {c_name}: {c_data.get('score', 0)}  | {c_data.get('reasoning', '')[:80]}")
        _write(lines)

    def error(self, context: str, resume_id: str, error: str):
        """Log a pipeline error."""
        lines = [
            f"[{_ts()}] ERROR  context={context}  resume_id={resume_id}",
            f"  {error}",
        ]
        _write(lines)


# Singleton — import and use directly
pdlog = PipelineDebugLog()
