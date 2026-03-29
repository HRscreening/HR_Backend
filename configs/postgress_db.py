from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import create_engine
from typing import AsyncGenerator
from sqlalchemy.orm import sessionmaker, declarative_base
from configs.env_config import DATABASE_URL
from contextlib import contextmanager
from sqlalchemy.orm import Session


# Supabase pooler (pgbouncer) — disable prepared statement cache
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"statement_cache_size": 0, "timeout": 30},  # 30s allows for SSL handshake overhead
    pool_pre_ping=True,  # Required for pgbouncer to avoid stale connections
    pool_recycle=300,
    pool_timeout=30,
    pool_size=5,
    max_overflow=10,
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
    pool_pre_ping=True,  # Required for pgbouncer
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