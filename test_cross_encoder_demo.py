#!/usr/bin/env python
"""
Quick demo script to test cross-encoder with 4-5 resumes.
This verifies the relevance scoring stage works correctly with small batches.

Usage:
    python test_cross_encoder_demo.py
"""

from src.pipelines.relevance_scorer import score_relevance_batch

# Sample JD (brief)
SAMPLE_JD = """
Senior Python Developer

We're looking for an experienced Python engineer with 5+ years building backend systems.
Strong expertise in FastAPI, PostgreSQL, and microservices architecture required.
Experience with machine learning pipelines and LLM applications is a plus.

Responsibilities:
- Design and implement scalable Python services
- Optimize database queries and API performance
- Collaborate with data scientists on ML pipelines
- Mentor junior engineers

Required Skills:
- Python 3.8+
- FastAPI or Django
- PostgreSQL
- Git and CI/CD
- System design fundamentals
"""

# Sample resumes (5 diverse examples)
SAMPLE_RESUMES = [
    {
        "resume_id": "res_001",
        "parsed_text": """
John Smith
Senior Backend Engineer

Experience:
- 7 years Python development at Google and Uber
- Designed microservices architecture for 1M+ RPS systems
- Built high-performance APIs with FastAPI and Django
- Optimized PostgreSQL queries reducing latency by 40%
- Led ML infrastructure team for recommendation engine

Skills: Python, FastAPI, PostgreSQL, Kubernetes, AWS, Redis
Education: BS Computer Science, Stanford University
        """
    },
    {
        "resume_id": "res_002",
        "parsed_text": """
Alice Johnson
Full Stack Developer

Experience:
- 3 years JavaScript/React development
- Built web applications with Node.js and Express
- MongoDB and Firebase databases
- Some Python scripting experience

Skills: JavaScript, React, Node.js, HTML/CSS, MongoDB
Education: Bootcamp Graduate
        """
    },
    {
        "resume_id": "res_003",
        "parsed_text": """
Bob Williams
DevOps/Infrastructure Engineer

Experience:
- 8 years infrastructure and deployment automation
- Kubernetes, Docker, Terraform expertise
- CI/CD pipeline design and optimization
- Some Python for infrastructure automation

Skills: Kubernetes, Docker, AWS, Terraform, Python (scripting)
Education: BS Systems Administration, UC Berkeley
        """
    },
    {
        "resume_id": "res_004",
        "parsed_text": """
Carol Davis
Data Engineer

Experience:
- 6 years building data pipelines at Meta and LinkedIn
- Python expertise with pandas, PySpark, and Airflow
- PostgreSQL and data warehouse optimization
- ETL pipeline design and implementation

Skills: Python, PySpark, PostgreSQL, Airflow, Data Warehousing
Education: MS Data Science, MIT
        """
    },
    {
        "resume_id": "res_005",
        "parsed_text": """
Diana Martinez
Frontend Developer

Experience:
- 4 years React and Vue.js development
- UI/UX implementation and responsive design
- Some backend experience with Python Flask
- REST API integration

Skills: React, Vue.js, JavaScript, Python (Flask), CSS, Design
Education: BS Web Development, San Jose State
        """
    }
]

def test_cross_encoder():
    print(f"Testing cross-encoder with {len(SAMPLE_RESUMES)} resumes")
    print("Cross-encoder will score all resumes and rank by relevance\n")

    selected, rejected = score_relevance_batch(
        resumes=SAMPLE_RESUMES,
        jd_text=SAMPLE_JD,
        top_n=3,
        min_score=0.01
    )

    print("=" * 70)
    print("CROSS-ENCODER RESULTS")
    print("=" * 70)

    print(f"\n✓ Selected for LLM Scoring ({len(selected)} resumes):")
    print("-" * 70)
    for resume in selected:
        rank = resume.get("rank", "?")
        score = resume.get("relevance_score")
        resume_id = resume["resume_id"]
        print(f"  [{rank}] {resume_id:15s} | Score: {score:.4f}")

    if rejected:
        print(f"\n✗ Pre-screened Out ({len(rejected)} resumes):")
        print("-" * 70)
        for result in rejected:
            print(f"  [{result.rank}] {result.resume_id:15s} | Score: {result.relevance_score:.4f}")
            print(f"       → {result.rejection_reason}\n")

    print("=" * 70)
    print(f"Summary: {len(selected)} selected, {len(rejected)} pre-screened")
    print("\n💡 The cross-encoder scored all {0} resumes and selected the top {1}".format(
        len(SAMPLE_RESUMES), len(selected)
    ))
    print("=" * 70)


if __name__ == "__main__":
    test_cross_encoder()
