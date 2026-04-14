"""
Database Engine - Async SQLAlchemy setup
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL


class Base(DeclarativeBase):
    """Base class cho tất cả models"""
    pass


# Tạo async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # True để debug SQL queries
)

# Session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Khởi tạo database - tạo tất cả bảng"""
    from database import models  # noqa: F401 - Import để register models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Tạo session mới"""
    async with async_session() as session:
        yield session
