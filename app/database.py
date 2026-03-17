"""
app/database.py
===============
SQLAlchemy database engine, session factory, and dependency injection.
 
Two engines are created:
  - sync_engine  : used by Alembic migrations only
  - async_engine : used by FastAPI route handlers
 
The app uses async by default because FastAPI is an async framework.
Alembic cannot use async, so it gets its own sync engine.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Base class — all ORM models inherit from this

class Base(DeclarativeBase):
    """
    Every SQLAlchemy model in models/base.py inherits from this class.
    It holds the shared metadata registry that Alembic reads to detect
    table changes when generating migrations.
    """
    pass


# Sync engine — Alembic only

sync_engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=settings.DEBUG,
    connect_args={"sslmode": "require"},
)


SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)

# Async engine — FastAPI route handlers
# SQLAlchemy needs postgresql+asyncpg:// for the async driver
# We replace the prefix so we don't need a separate env variable

async_db_url = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
)

async_engine = create_async_engine(
    async_db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=settings.DEBUG,
    connect_args={"sslmode": "require"},
)


AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# FastAPI dependency — inject a DB session into route handlers

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async database session.
    Automatically commits on success and rolls back on error.
 
    Usage in any route:
        from fastapi import Depends
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.database import get_db
 
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(MyModel))
    """

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Context manager — for background tasks and scripts outside FastAPI
@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions used outside of FastAPI's
    dependency injection system — for example in scheduled jobs (Phase 2).
 
    Usage:
        async with get_async_session() as session:
            result = await session.execute(select(MyModel))
    """


    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# Sync session — for scripts and Alembic
def get_sync_db() -> Session:
    """
    Sync session generator for use in plain Python scripts
    and Alembic migration helpers.
    """

    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Health check helper — used by /health/ready endpoint
async def check_db_connection() -> bool:
    """
    Runs a lightweight SELECT 1 query to confirm the database is reachable.
    Returns True if the connection succeeds, False if it fails.
    Called by the /health/ready endpoint in routers/health.py.
    """

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))

        logger.info("db_connection_ok")
        return True
    
    except Exception as exc:
        logger.error("db_connection_failed", error=str(exc))
        return False



