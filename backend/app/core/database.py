from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,          # Đặt True khi cần debug SQL
    pool_pre_ping=True,  # Kiểm tra kết nối trước khi dùng
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class cho tất cả ORM models."""
    pass


async def get_db() -> AsyncSession:  # type: ignore[override]
    """FastAPI dependency – trả về AsyncSession cho mỗi request."""
    async with AsyncSessionLocal() as session:
        yield session
