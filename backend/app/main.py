from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware
from strawberry.fastapi import GraphQLRouter

from app.api.v1 import router as api_router
from app.config import settings
from app.database import get_db, engine
from app.graphql.schema import schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    # runs on startup
    yield
    # runs on shutdown


app = FastAPI(
    title="ViewPilot",
    debug=settings.debug,
    lifespan=lifespan,
)

# signs the session cookie so it can't be tampered with
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

# lets the nuxt frontend talk to this api — in debug mode allow all origins for easy local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [settings.frontend_url],
    allow_credentials=not settings.debug,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_graphql_context(request: Request) -> dict:
    """injects request + db session into every graphql resolver via info.context."""
    async for db in get_db():
        return {"request": request, "db": db}


graphql_router = GraphQLRouter(schema, context_getter=get_graphql_context)

app.include_router(api_router)
app.include_router(graphql_router, prefix="/graphql")


@app.get("/health")
async def health():
    checks = {}

    # check postgres — just run a trivial query
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"error: {e}"

    # check redis — ping it
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, **checks}
