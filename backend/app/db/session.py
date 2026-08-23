import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.observability.metrics import (
    DB_CONNECTION_ERRORS,
    DB_POOL_AVAILABLE,
    DB_POOL_CAPACITY,
    DB_POOL_CHECKED_OUT,
    DB_POOL_OVERFLOW,
    DB_POOL_SIZE,
    DB_POOL_WAIT,
)

settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout_seconds,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def update_pool_metrics() -> None:
    pool = engine.sync_engine.pool
    for metric, getter in (
        (DB_POOL_SIZE, pool.size),
        (DB_POOL_CHECKED_OUT, pool.checkedout),
        (DB_POOL_AVAILABLE, pool.checkedin),
        (DB_POOL_OVERFLOW, pool.overflow),
    ):
        try:
            metric.set(max(0, getter()))
        except (AttributeError, TypeError):
            metric.set(0)


@event.listens_for(engine.sync_engine.pool, "checkout")
@event.listens_for(engine.sync_engine.pool, "checkin")
def _pool_connection_changed(*_args) -> None:
    update_pool_metrics()


@event.listens_for(engine.sync_engine.pool, "invalidate")
def _pool_connection_invalidated(*_args) -> None:
    DB_CONNECTION_ERRORS.inc()
    update_pool_metrics()


update_pool_metrics()
DB_POOL_CAPACITY.set(settings.database_pool_size + settings.database_max_overflow)


async def database_health() -> str:
    started = asyncio.get_running_loop().time()
    try:
        async with asyncio.timeout(settings.database_health_timeout_seconds):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        return "ok"
    except (TimeoutError, OSError, SQLAlchemyError):
        DB_CONNECTION_ERRORS.inc()
        return "down"
    finally:
        DB_POOL_WAIT.observe(asyncio.get_running_loop().time() - started)
        update_pool_metrics()


async def close_session(session: AsyncSession | None) -> None:
    if session is None:
        return
    if hasattr(session, "rollback"):
        try:
            await session.rollback()
        except SQLAlchemyError:
            pass
    if hasattr(session, "close"):
        try:
            await session.close()
        except SQLAlchemyError:
            pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
