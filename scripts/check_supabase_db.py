#!/usr/bin/env python3
"""
Check Supabase (PostgreSQL) connection. Edit the variables below and run:
  python scripts/check_supabase_db.py
"""
import asyncio
import sys
from urllib.parse import quote_plus

# --- Set your Supabase DB connection here ---
# Use Connection Pooler (avoids timeout); get from Supabase → Settings → Database → Connection string (Transaction).
# Pooler: host below, port 6543, user = postgres.<project-ref>
SUPABASE_HOST = "aws-0-ap-south-1.pooler.supabase.com"
SUPABASE_PORT = 6543
SUPABASE_USER = "postgres.akzgqvcsmazwckhprzvm"
SUPABASE_PASSWORD = "pCKOQQjHHEm6kOFI"
SUPABASE_DB = "postgres"

# Build DSN (asyncpg uses postgresql://)
dsn = (
    f"postgresql://{SUPABASE_USER}:{quote_plus(SUPABASE_PASSWORD)}"
    f"@{SUPABASE_HOST}:{SUPABASE_PORT}/{SUPABASE_DB}"
)


# Connection timeout (seconds). Increase if on slow/VPN network.
CONNECT_TIMEOUT = 25


async def check():
    try:
        import asyncpg
    except ImportError:
        print("FAIL: asyncpg not installed. Run: pip install asyncpg")
        sys.exit(1)

    print(f"Connecting to {SUPABASE_HOST}:{SUPABASE_PORT} (timeout {CONNECT_TIMEOUT}s)...")

    try:
        conn = await asyncpg.connect(dsn=dsn, timeout=CONNECT_TIMEOUT)
        try:
            row = await conn.fetchrow("SELECT 1 AS one, current_database() AS db, version() AS ver")
            print("OK: Connected to Supabase PostgreSQL")
            print(f"    database: {row['db']}")
            print(f"    version:  {row['ver'].split(',')[0]}")
        finally:
            await conn.close()
        return 0
    except asyncio.TimeoutError:
        _print_timeout_hints()
        return 1
    except Exception as e:
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            print(f"FAIL: {type(e).__name__}: {e}")
            _print_timeout_hints()
        else:
            print(f"FAIL: {type(e).__name__}: {e}")
        return 1


def _print_timeout_hints():
    print("  • Check Supabase dashboard: project not paused, DB is running.")
    print("  • Try Connection Pooler: Supabase → Settings → Database → Connection string (Session/Transaction).")
    print("  • If on VPN/corporate network, try without VPN or allow outbound to port 5432.")


if __name__ == "__main__":
    exit_code = asyncio.run(check())
    sys.exit(exit_code)
