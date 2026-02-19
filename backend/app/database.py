from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# opens the connection to postgres
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # logs sql queries to console in dev, handy for debugging
)

# each request gets its own db workspace/session from this
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,  # keeps data accessible after saving
)


# every database model (table) inherits from this
class Base(DeclarativeBase):
    pass


# hands a fresh db session to each route, then closes it when the request is done
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
