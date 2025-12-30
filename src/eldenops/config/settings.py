"""Application settings using Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/eldenops"
    )
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")

    # Discord
    discord_bot_token: SecretStr = Field(default="")
    discord_client_id: str = ""
    discord_client_secret: SecretStr = Field(default="")
    discord_redirect_uri: str = "http://localhost:8000/api/v1/auth/discord/callback"

    # Security
    jwt_secret_key: SecretStr = Field(default="change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    encryption_key: SecretStr = Field(default="change-me-in-production")

    # AI Providers (defaults, tenants can override)
    anthropic_api_key: SecretStr = Field(default="")
    default_claude_model: str = "claude-sonnet-4-20250514"

    openai_api_key: SecretStr = Field(default="")
    default_openai_model: str = "gpt-4o"

    google_api_key: SecretStr = Field(default="")
    default_gemini_model: str = "gemini-pro"

    deepseek_api_key: SecretStr = Field(default="")
    default_deepseek_model: str = "deepseek-chat"

    # GitHub
    github_app_id: str = ""
    github_app_private_key: SecretStr = Field(default="")
    github_webhook_secret: SecretStr = Field(default="")

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "production"

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL for Alembic."""
        return str(self.database_url).replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
