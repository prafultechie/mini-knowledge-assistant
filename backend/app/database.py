from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from app.models import Document, Chunk, QuestionLog  # noqa: F401
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        # create_all does not add columns to an existing SQLite database.
        if engine.url.get_backend_name() == "sqlite":
            result = await connection.exec_driver_sql("PRAGMA table_info(chunks)")
            columns = {row[1] for row in result.fetchall()}
            if "embedding_json" not in columns:
                await connection.exec_driver_sql(
                    "ALTER TABLE chunks ADD COLUMN embedding_json TEXT"
                )
