from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "E-Commerce GraphQL API"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True
    allowed_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── Security ─────────────────────────────────────────────────────────────
    secret_key: str = "change-me-in-production-use-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://ecom_user:ecom_pass@localhost:5432/ecommerce_db"
    )

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Email ─────────────────────────────────────────────────────────────────
    mail_username: str = ""
    mail_password: str = ""
    mail_from: str = "noreply@ecommerce.dev"
    mail_server: str = "smtp.gmail.com"
    mail_port: int = 587
    mail_tls: bool = True
    mail_ssl: bool = False

    # ── AI Recommendations ────────────────────────────────────────────────────
    recommendation_cache_ttl: int = 3600
    min_interactions_for_cf: int = 5

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
