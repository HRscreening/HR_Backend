"""
Shared fixtures and sample data for Phase 1 tests.

Load order matters: .env must be loaded before any app imports
because LLM clients, DB configs etc. read env vars at import time.
"""

# ── Load env FIRST ─────────────────────────────────────────────────────────────
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── Std imports ────────────────────────────────────────────────────────────────
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# ── App imports (safe after load_dotenv) ───────────────────────────────────────
from src.schemas.user_schemas import (
    LLMScoringOnlyOutput,
    SectionRawScore,
    CriterionRawScore,
    SubCriterionRawScore,
    GroundingCriterionData,
    CandidateInfoSchema,
)

# ── Paths ──────────────────────────────────────────────────────────────────────
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_JD_PDF  = FIXTURES_DIR / "sample_jd.pdf"
SAMPLE_RESUME_PDF = FIXTURES_DIR / "sample_resume.pdf"


# ═══════════════════════════════════════════════════════════════════════════════
# Sample text data (in-memory — no files needed)
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_JD_TEXT = """
Senior Backend Engineer

We are seeking a highly skilled Senior Backend Engineer to join our growing team.

Requirements:
- 5+ years of professional software development experience
- Strong proficiency in Python and FastAPI
- Experience with PostgreSQL and Redis
- Knowledge of AWS services (EC2, S3, Lambda)
- Bachelor's degree in Computer Science or related field (required)

Preferred Qualifications:
- Experience with Docker and Kubernetes
- Familiarity with microservices architecture
- Strong communication skills

Responsibilities:
- Design and implement scalable backend systems
- Lead technical discussions and code reviews
- Mentor junior engineers

Constraints:
- Location: San Francisco, CA (Hybrid - 3 days/week)
- Must be authorized to work in the United States
- Salary: $150,000 - $200,000 per year
"""

SAMPLE_RESUME_TEXT = """
John Smith
john.smith@email.com | +1 (555) 234-5678 | San Francisco, CA

SUMMARY
Experienced backend engineer with 7 years building scalable Python services.
Strong expertise in FastAPI, PostgreSQL, and AWS infrastructure.

EXPERIENCE
Senior Software Engineer — TechCorp (2020–Present)
- Built microservices with FastAPI handling 10M+ requests/day
- Optimized PostgreSQL queries, reducing p99 latency by 40%
- Led team of 5 engineers, conducted weekly code reviews
- AWS certified; managed EC2, S3, Lambda infrastructure

Software Engineer — StartupXYZ (2017–2020)
- Developed REST APIs in Python/Flask
- Migrated on-prem DB to AWS RDS PostgreSQL
- Implemented Redis caching layer for session management

EDUCATION
B.S. Computer Science — UC Berkeley (2017)

SKILLS
Python, FastAPI, Flask, PostgreSQL, Redis, AWS, Docker, Kubernetes
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Sample rubric (minimal but valid — matches the pipeline schema)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_rubric_criteria():
    """A minimal but fully valid rubric criteria dict as stored in the DB."""
    return {
        "schema_version": 2,
        "sections": [
            {
                "key": "required_skills",
                "label": "Required Skills",
                "weight": 70,
                "importance": 9,
                "criteria": [
                    {
                        "name": "python_fastapi",
                        "display_name": "Python & FastAPI",
                        "description": "Proficiency in Python and FastAPI framework",
                        "importance": 9,
                        "weight": 50,
                        "priority": 1,
                        "requirement_level": "must",
                        "value": None,
                        "value_type": "none",
                        "sub_criteria": None,
                    },
                    {
                        "name": "postgresql_redis",
                        "display_name": "PostgreSQL & Redis",
                        "description": "Database and caching experience",
                        "importance": 7,
                        "weight": 30,
                        "priority": 2,
                        "requirement_level": "must",
                        "value": None,
                        "value_type": "none",
                        "sub_criteria": None,
                    },
                    {
                        "name": "aws",
                        "display_name": "AWS Services",
                        "description": "Experience with AWS EC2, S3, Lambda",
                        "importance": 5,
                        "weight": 20,
                        "priority": 3,
                        "requirement_level": "should",
                        "value": None,
                        "value_type": "none",
                        "sub_criteria": None,
                    },
                ],
            },
            {
                "key": "preferred_qualifications",
                "label": "Preferred Qualifications",
                "weight": 30,
                "importance": 5,
                "criteria": [
                    {
                        "name": "docker_kubernetes",
                        "display_name": "Docker & Kubernetes",
                        "description": "Container orchestration experience",
                        "importance": 6,
                        "weight": 60,
                        "priority": 1,
                        "requirement_level": "nice",
                        "value": None,
                        "value_type": "none",
                        "sub_criteria": None,
                    },
                    {
                        "name": "communication",
                        "display_name": "Communication Skills",
                        "description": "Strong written and verbal communication",
                        "importance": 4,
                        "weight": 40,
                        "priority": 2,
                        "requirement_level": "nice",
                        "value": None,
                        "value_type": "none",
                        "sub_criteria": None,
                    },
                ],
            },
        ],
    }


@pytest.fixture
def sample_rubric_with_sub_criteria():
    """Rubric with sub-criteria to test sub-criteria weight aggregation."""
    return {
        "schema_version": 2,
        "sections": [
            {
                "key": "technical_skills",
                "label": "Technical Skills",
                "weight": 100,
                "importance": 10,
                "criteria": [
                    {
                        "name": "backend",
                        "display_name": "Backend Development",
                        "description": "Backend skills",
                        "importance": 8,
                        "weight": 60,
                        "priority": 1,
                        "requirement_level": "must",
                        "value": None,
                        "value_type": "none",
                        "sub_criteria": [
                            {
                                "name": "python",
                                "display_name": "Python",
                                "importance": 5,
                                "weight": 60,
                                "value": None,
                                "value_type": "none",
                            },
                            {
                                "name": "fastapi",
                                "display_name": "FastAPI",
                                "importance": 3,
                                "weight": 40,
                                "value": None,
                                "value_type": "none",
                            },
                        ],
                    },
                    {
                        "name": "database",
                        "display_name": "Database",
                        "description": "Database skills",
                        "importance": 5,
                        "weight": 40,
                        "priority": 2,
                        "requirement_level": "should",
                        "value": None,
                        "value_type": "none",
                        "sub_criteria": None,
                    },
                ],
            }
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Sample LLM output — deterministic, no real LLM needed
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_llm_scoring_output():
    """
    A pre-built LLMScoringOnlyOutput that matches the sample_rubric_criteria fixture.
    Used to test _post_process_score without calling the real LLM.
    """
    return LLMScoringOnlyOutput(
        ai_analysis={
            "good_points": [
                "7 years of Python experience with FastAPI at scale",
                "AWS certified with hands-on EC2, S3, Lambda experience",
                "Strong leadership: led team of 5 engineers",
            ],
            "bad_points": [
                "No explicit mention of Kubernetes in production",
                "Communication skills not demonstrated with specific examples",
            ],
        },
        ai_confidence=0.88,
        sections={
            "required_skills": SectionRawScore(
                criteria={
                    "python_fastapi": CriterionRawScore(
                        score=90.0,
                        reasoning="7 years Python, FastAPI at 10M+ req/day — exceptional evidence",
                        sub_criteria={},
                    ),
                    "postgresql_redis": CriterionRawScore(
                        score=82.0,
                        reasoning="PostgreSQL query optimization and Redis caching both documented",
                        sub_criteria={},
                    ),
                    "aws": CriterionRawScore(
                        score=85.0,
                        reasoning="AWS certified, managed EC2/S3/Lambda — strong match",
                        sub_criteria={},
                    ),
                }
            ),
            "preferred_qualifications": SectionRawScore(
                criteria={
                    "docker_kubernetes": CriterionRawScore(
                        score=70.0,
                        reasoning="Docker mentioned in skills but no Kubernetes in production context",
                        sub_criteria={},
                    ),
                    "communication": CriterionRawScore(
                        score=55.0,
                        reasoning="Led code reviews and team but no specific communication examples",
                        sub_criteria={},
                    ),
                }
            ),
        },
        grounding_data={
            "required_skills": {
                "python_fastapi": GroundingCriterionData(
                    jd_requirement="Strong proficiency in Python and FastAPI",
                    evidence=[
                        "Built microservices with FastAPI handling 10M+ requests/day",
                        "7 years building scalable Python services",
                    ],
                    match_assessment="exceeds",
                ),
                "postgresql_redis": GroundingCriterionData(
                    jd_requirement="Experience with PostgreSQL and Redis",
                    evidence=[
                        "Optimized PostgreSQL queries, reducing p99 latency by 40%",
                        "Implemented Redis caching layer for session management",
                    ],
                    match_assessment="strong",
                ),
                "aws": GroundingCriterionData(
                    jd_requirement="Knowledge of AWS services (EC2, S3, Lambda)",
                    evidence=["AWS certified; managed EC2, S3, Lambda infrastructure"],
                    match_assessment="strong",
                ),
            },
            "preferred_qualifications": {
                "docker_kubernetes": GroundingCriterionData(
                    jd_requirement="Experience with Docker and Kubernetes",
                    evidence=["Docker, Kubernetes listed in skills"],
                    match_assessment="partial",
                ),
                "communication": GroundingCriterionData(
                    jd_requirement="Strong communication skills",
                    evidence=["Led team of 5 engineers, conducted weekly code reviews"],
                    match_assessment="partial",
                ),
            },
        },
        distinguishing_factors=[
            "Handles 10M+ requests/day — rare scale signal",
            "AWS certified (not just self-reported)",
            "40% p99 latency reduction — quantified impact",
        ],
    )


@pytest.fixture
def sample_llm_scoring_output_with_sub_criteria():
    """LLM output with sub-criteria scores, matching sample_rubric_with_sub_criteria."""
    return LLMScoringOnlyOutput(
        ai_analysis={"good_points": ["Strong Python"], "bad_points": ["Limited scope"]},
        ai_confidence=0.75,
        sections={
            "technical_skills": SectionRawScore(
                criteria={
                    "backend": CriterionRawScore(
                        score=80.0,
                        reasoning="Good backend skills overall",
                        sub_criteria={
                            "python": SubCriterionRawScore(score=90.0, reasoning="Excellent Python"),
                            "fastapi": SubCriterionRawScore(score=75.0, reasoning="Solid FastAPI"),
                        },
                    ),
                    "database": CriterionRawScore(
                        score=70.0,
                        reasoning="PostgreSQL experience documented",
                        sub_criteria={},
                    ),
                }
            ),
        },
        grounding_data={
            "technical_skills": {
                "backend": GroundingCriterionData(
                    jd_requirement="Backend development skills",
                    evidence=["FastAPI microservices", "Python APIs"],
                    match_assessment="strong",
                ),
                "database": GroundingCriterionData(
                    jd_requirement="Database skills",
                    evidence=["PostgreSQL optimization"],
                    match_assessment="strong",
                ),
            }
        },
        distinguishing_factors=["Strong Python background"],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Mock LLM — returns deterministic rubric JSON, avoids real API calls
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_rubric_llm_response():
    """Raw JSON string that a mocked LLM would return for rubric generation."""
    rubric = {
        "domain": "software_engineering",
        "domain_confidence": 0.9,
        "threshold_score": 65,
        "sections": [
            {
                "key": "required_skills",
                "label": "Required Skills",
                "importance": 9,
                "criteria": [
                    {
                        "name": "python_fastapi",
                        "display_name": "Python & FastAPI",
                        "description": "Proficiency in Python and FastAPI",
                        "importance": 9,
                        "requirement_level": "must",
                        "value": None,
                        "value_type": "none",
                        "sub_criteria": None,
                    },
                    {
                        "name": "postgresql",
                        "display_name": "PostgreSQL",
                        "description": "Database experience",
                        "importance": 7,
                        "requirement_level": "must",
                        "value": None,
                        "value_type": "none",
                        "sub_criteria": None,
                    },
                ],
            },
            {
                "key": "preferred_qualifications",
                "label": "Preferred Qualifications",
                "importance": 5,
                "criteria": [
                    {
                        "name": "docker_kubernetes",
                        "display_name": "Docker & Kubernetes",
                        "description": "Container experience",
                        "importance": 6,
                        "requirement_level": "nice",
                        "value": None,
                        "value_type": "none",
                        "sub_criteria": None,
                    }
                ],
            },
        ],
    }
    return json.dumps(rubric)
