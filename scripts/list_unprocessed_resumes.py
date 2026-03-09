#!/usr/bin/env python3
"""
List resumes that are not yet PARSED (or in ERROR).
Run from HR_Backend: python scripts/list_unprocessed_resumes.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from configs.postgress_db import sync_engine
from sqlalchemy import text

QUERY = """
SELECT
    r.id AS resume_id,
    r.status AS resume_status,
    c.full_name,
    c.email,
    a.id AS application_id,
    j.title AS job_title
FROM resumes r
JOIN applications a ON a.id = r.application_id
LEFT JOIN candidates c ON c.id = a.candidate_id
JOIN jobs j ON j.id = a.job_id
WHERE r.status::text NOT IN ('PARSED', 'SCORED', 'QUEUED_FOR_SCORING', 'SCORING_IN_PROGRESS')
ORDER BY r.uploaded_at;
"""


def main():
    print("Connecting to DB...")
    with sync_engine.connect() as conn:
        rows = conn.execute(text(QUERY)).fetchall()
    if not rows:
        print("No unprocessed resumes found.")
        return
    print(f"\n{len(rows)} resume(s) not yet parsed:\n")
    for r in rows:
        name = r.full_name or "(no name)"
        email = r.email or "(no email)"
        print(f"  • {name} <{email}> — status: {r.resume_status} — job: {r.job_title}")


if __name__ == "__main__":
    main()
