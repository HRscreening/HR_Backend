from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import create_engine
from typing import AsyncGenerator
from sqlalchemy.orm import sessionmaker, declarative_base
from configs.env_config import DATABASE_URL
from contextlib import contextmanager
from sqlalchemy.orm import Session


# Supabase pooler (port 6543) uses pgbouncer transaction mode — disable prepared statement cache
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"statement_cache_size": 0},
    # Pooler connections can be dropped; pre-ping avoids stale connections causing runtime errors
    pool_pre_ping=True,
    # Recycle periodically to reduce "connection closed" mid-operation issues
    pool_recycle=300,
)




async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)



async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
        
def get_sync_db_url(async_url: str) -> str:
    return async_url.replace("+asyncpg", "")



SYNC_DATABASE_URL = get_sync_db_url(DATABASE_URL)

sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True
)

sync_session_maker = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False
)




@contextmanager
def get_sync_db():
    db = sync_session_maker()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

Base = declarative_base()