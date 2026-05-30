"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 2328.io
    gateway_base_url: str = "https://api.2328.io/api"
    gateway_project_uuid: str = "test-project"
    gateway_api_key: str = "test-api-key"
    gateway_payout_api_key: str = "test-payout-key"
    gateway_user_agent: str = "tg-crypto-pay/0.1 (+https://example.com)"

    public_base_url: str = "http://localhost:8000"

    # Telegram
    telegram_bot_token: str = "test-bot-token"

    # App
    database_url: str = "sqlite+aiosqlite:///./dev.db"
    default_markup_percent: float = 3.0
    supported_crypto: str = "USDT,TON,BTC,ETH,TRX"

    @property
    def supported_crypto_list(self) -> list[str]:
        return [c.strip().upper() for c in self.supported_crypto.split(",") if c.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
