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

    # Frontend base URL — used for OAuth redirects
    frontend_url: str = Field("http://localhost:3000", alias="FRONTEND_URL")

    # GitHub OAuth
    github_client_id: str | None = Field(None, alias="GITHUB_CLIENT_ID")
    github_client_secret: str | None = Field(None, alias="GITHUB_CLIENT_SECRET")

    # Demo mode — blocks all mutating requests, for public read-only demo instances
    demo_mode: bool = Field(False, alias="DEMO_MODE")

    # Monetization guardrails — software boundaries only, no billing logic
    tier: Literal["free", "pro", "team"] = Field("free", alias="TRECO_TIER")
    max_parallel_agents: int = Field(1, alias="MAX_PARALLEL_AGENTS")

    # Worktree isolation
    keep_worktree_on_error: bool = Field(True, alias="KEEP_WORKTREE_ON_ERROR")

    # Deviation detection
    stuck_after_seconds: int = Field(600, alias="STUCK_AFTER_SECONDS")
    token_spike_multiplier: float = Field(5.0, alias="TOKEN_SPIKE_MULTIPLIER")

    # $/1M-token price table for cost_usd_per_ticket, matched by model prefix
    model_prices: dict[str, dict[str, float]] = Field(
        default={
            "claude-haiku": {"in": 1.0, "out": 5.0},
            "claude-sonnet": {"in": 3.0, "out": 15.0},
            "claude-opus": {"in": 15.0, "out": 75.0},
            "gpt-4o-mini": {"in": 0.15, "out": 0.6},
            "gpt-4o": {"in": 2.5, "out": 10.0},
        },
        alias="MODEL_PRICES",
    )

    model_config = SettingsConfigDict(env_file=".env", populate_by_name=True)


settings = Settings()
