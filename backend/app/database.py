from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

database_url = settings.DATABASE_URL
if settings.VERCEL and not database_url.startswith(("postgres://", "postgresql://", "postgresql+asyncpg://")):
    raise RuntimeError("Vercel deployments require DATABASE_URL to point to managed PostgreSQL storage")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

if database_url.startswith("postgresql+asyncpg://"):
    # Hosted-provider URLs often include libpq's sslmode parameter; asyncpg
    # expects TLS through its ssl argument instead. Neon also emits
    # channel_binding=require, which asyncpg does not accept as a URL option.
    parts = urlsplit(database_url)
    unsupported_asyncpg_options = {"sslmode", "channel_binding"}
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in unsupported_asyncpg_options
    ]
    database_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

engine_options = {"echo": False}
if database_url.startswith("postgresql+asyncpg://"):
    engine_options.update(pool_pre_ping=True, pool_recycle=300)
    if settings.VERCEL:
        engine_options["connect_args"] = {"ssl": "require"}

engine = create_async_engine(database_url, **engine_options)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    from app import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
