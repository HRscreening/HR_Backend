from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from typing import AsyncGenerator
from sqlalchemy.orm import sessionmaker, declarative_base
from configs.env_config import DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)




async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
