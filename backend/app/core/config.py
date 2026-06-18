from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = Field("sqlite+aiosqlite:///./treco.db", alias="DATABASE_URL")
    database_mode: Literal["sqlite", "postgres"] = Field("sqlite", alias="DATABASE_MODE")

    # Auth — defaults to "dev-secret" so pytest doesn't require env setup
    jwt_secret: str = Field("dev-secret-change-in-production", alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 1 week

    # LLM (for criteria extraction)
    anthropic_api_key: str | None = Field(None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    llm_provider: Literal["anthropic", "openai"] = Field("anthropic", alias="LLM_PROVIDER")

    # CORS
    cors_origins: list[str] = Field(["http://localhost:3000", "http://localhost:8001"], alias="CORS_ORIGINS")

    # Agent SDK
    sdk_key_prefix: str = "treco_"

    # Base URL spawned agent subprocesses use to reach this backend
    backend_url: str = Field("http://localhost:8001", alias="BACKEND_URL")

    model_config = SettingsConfigDict(env_file=".env", populate_by_name=True)


settings = Settings()
