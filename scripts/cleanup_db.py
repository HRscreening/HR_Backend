#!/usr/bin/env python3
"""
Truncate resume/application-related tables for a fresh start.
Run from HR_Backend: python scripts/cleanup_db.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from configs.postgress_db import sync_engine
from sqlalchemy import text

# Parents first; CASCADE truncates dependent tables (scores, resumes)
TABLES = [
    "applications",  # CASCADE truncates scores, resumes
    "documents",
    "bulk_upload_batches",
]


def main():
    print("Connecting to DB...")
    with sync_engine.connect() as conn:
        try:
            for table in TABLES:
                conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                conn.commit()
                print(f"  Truncated {table}")
        except Exception as e:
            conn.rollback()
            print(f"Error: {e}")
            sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
