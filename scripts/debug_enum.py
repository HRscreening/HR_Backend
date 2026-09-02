
import asyncio
from configs.postgress_db import engine
from sqlalchemy import text

async def check():
    try:
        async with engine.connect() as conn:
            res = await conn.execute(text("SELECT n.nspname as schema, t.typname as type, array_agg(e.enumlabel ORDER BY e.enumsortorder) as values FROM pg_type t JOIN pg_enum e ON t.oid = e.enumtypid JOIN pg_namespace n ON n.oid = t.typnamespace WHERE t.typname = 'reminder_status_enum' GROUP BY n.nspname, t.typname;"))
            row = res.fetchone()
            if row:
                print(f"Enum {row[1]} in schema {row[0]} has values: {row[2]}")
            else:
                print("reminder_status_enum not found in pg_enum")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(check())
