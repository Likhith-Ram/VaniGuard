import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from typing import AsyncGenerator

# Database credentials (using specific prefixes to avoid global host variable collisions)
POSTGRES_USER = os.getenv("VANIGUARD_DB_USER", "vaniguard")
POSTGRES_PASSWORD = os.getenv("VANIGUARD_DB_PASSWORD", "vanipass123")
POSTGRES_DB = os.getenv("VANIGUARD_DB_NAME", "vaniguard_db")
POSTGRES_HOST = os.getenv("VANIGUARD_DB_HOST", "localhost")
POSTGRES_PORT = os.getenv("VANIGUARD_DB_PORT", "5433")

DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Enterprise-grade connection pooling
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

async def get_db() -> AsyncGenerator:
    """
    Asynchronous dependency for database sessions.
    Automatically handles commit and rollback semantics.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
