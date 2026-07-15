from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import get_settings
from app.core.logging import logger

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.debug)
logger.debug("Database engine created (echo=%s)", settings.debug)

SessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()


async def get_db():
    async with SessionLocal() as session:
        yield session


async def init_db():
    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")
