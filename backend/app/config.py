from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# find .env at the project root regardless of where alembic/uvicorn is run from
_env_file = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Google OAuth
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    # Gemini API
    gemini_api_key: str = ""

    # App security
    secret_key: str

    # App config
    debug: bool = False
    frontend_url: str = "http://localhost:3000"

    # YouTube Data API — secondary access for public data lookups without user authentication
    youtube_api_key: str = ""

    model_config = SettingsConfigDict(env_file=str(_env_file), extra="ignore")


# Single shared instance — import this everywhere
settings = Settings()
