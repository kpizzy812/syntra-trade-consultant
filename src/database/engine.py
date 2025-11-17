"""
Database engine configuration for Syntra Trade Consultant Bot

Async SQLAlchemy 2.0 setup with connection pooling
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool

from config.config import DATABASE_URL, ENVIRONMENT
from src.database.models import Base

logger = logging.getLogger(__name__)


# Global engine and session maker
engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Create and configure async database engine

    Returns:
        Configured AsyncEngine instance
    """
    global engine

    if engine is None:
        # Production vs Development settings
        is_production = ENVIRONMENT == "production"

        engine = create_async_engine(
            DATABASE_URL,
            # Connection pooling
            poolclass=AsyncAdaptedQueuePool,
            pool_size=10 if is_production else 5,
            max_overflow=20 if is_production else 10,
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,  # Recycle connections every hour
            # Logging (disabled - using loguru)
            echo=False,  # Don't spam SQL queries
            echo_pool=False,  # Don't log pool operations
            # Performance
            connect_args={
                "statement_cache_size": 0,  # Disable prepared statement cache
                "server_settings": {
                    "application_name": "syntra_bot",
                    "jit": "off",  # Disable JIT for better performance with small queries
                },
            },
        )

        logger.info(
            f"Database engine created - Environment: {ENVIRONMENT}, "
            f"Pool size: {engine.pool.size()}, Max overflow: {engine.pool.overflow()}"
        )

    return engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """
    Create async session maker

    Returns:
        Configured async_sessionmaker instance
    """
    global AsyncSessionLocal

    if AsyncSessionLocal is None:
        eng = get_engine()
        AsyncSessionLocal = async_sessionmaker(
            eng,
            class_=AsyncSession,
            expire_on_commit=False,  # Important for async!
            autoflush=False,
            autocommit=False,
        )

        logger.info("Session maker created")

    return AsyncSessionLocal


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database session

    Usage in handlers:
        async def handler(session: AsyncSession = Depends(get_session)):
            ...

    Yields:
        AsyncSession instance
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Session error: {e}", exc_info=True)
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database - create all tables

    WARNING: This creates tables if they don't exist.
    For production, use Alembic migrations instead.
    """
    eng = get_engine()

    logger.info("Creating database tables...")

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")


async def drop_db() -> None:
    """
    Drop all database tables

    WARNING: This deletes all data! Use with caution.
    Only for development/testing.
    """
    if ENVIRONMENT == "production":
        raise RuntimeError("Cannot drop database in production environment!")

    eng = get_engine()

    logger.warning("Dropping all database tables...")

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    logger.warning("Database tables dropped")


async def dispose_engine() -> None:
    """
    Dispose database engine and close all connections

    Call this on application shutdown
    """
    global engine, AsyncSessionLocal

    if engine is not None:
        await engine.dispose()
        logger.info("Database engine disposed")
        engine = None
        AsyncSessionLocal = None


# For testing and manual operations
async def check_connection() -> bool:
    """
    Check database connection

    Returns:
        True if connection successful, False otherwise
    """
    try:
        eng = get_engine()
        async with eng.connect() as conn:
            await conn.execute("SELECT 1")
        logger.info("Database connection check: OK")
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    # Test database connection
    import asyncio
    from config.logging import setup_logging

    setup_logging()

    async def test():
        print("Testing database connection...")

        # Check connection
        is_connected = await check_connection()
        print(f'Connection: {"✅ OK" if is_connected else "❌ FAILED"}')

        # Initialize tables (use Alembic in production!)
        if is_connected:
            print("\nCreating tables...")
            await init_db()
            print("✅ Tables created")

        # Cleanup
        await dispose_engine()
        print("\n✅ Engine disposed")

    asyncio.run(test())
