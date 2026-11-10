from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import config
from db.models import Base

engine = create_async_engine(config.POSTGRES_DSN, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)