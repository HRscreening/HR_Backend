#!/usr/bin/env python3
"""
Delete applications for a job that have no scores (stuck in "Processing...").
Run from HR_Backend: python scripts/cleanup_stuck_applications.py <job_id>

Example: python scripts/cleanup_stuck_applications.py 80119f29-5c91-4ab2-aaa3-e76e7c14656c
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from configs.postgress_db import sync_engine
from sqlalchemy import text


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/cleanup_stuck_applications.py <job_id>")
        print("Example: python scripts/cleanup_stuck_applications.py 80119f29-5c91-4ab2-aaa3-e76e7c14656c")
        sys.exit(1)

    job_id = sys.argv[1].strip()

    print(f"Finding applications for job {job_id} with no scores...")
    with sync_engine.connect() as conn:
        # Count stuck applications
        count_result = conn.execute(
            text("""
                SELECT COUNT(*) FROM applications a
                WHERE a.job_id = :job_id
                  AND a.deleted_at IS NULL
                  AND NOT EXISTS (SELECT 1 FROM scores s WHERE s.application_id = a.id)
            """),
            {"job_id": job_id},
        )
        count = count_result.scalar_one()

        if count == 0:
            print("No stuck applications found.")
            return

        print(f"Soft-deleting {count} application(s)...")
        conn.execute(
            text("""
                UPDATE applications
                SET deleted_at = NOW()
                WHERE job_id = :job_id
                  AND deleted_at IS NULL
                  AND NOT EXISTS (SELECT 1 FROM scores s WHERE s.application_id = applications.id)
            """),
            {"job_id": job_id},
        )
        conn.commit()
    print("Done.")


if __name__ == "__main__":
    main()
