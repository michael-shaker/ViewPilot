from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1 import router as api_router
from app.config import settings


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

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
