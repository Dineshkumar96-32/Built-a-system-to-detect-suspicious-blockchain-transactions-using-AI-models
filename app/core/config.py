"""
app/core/config.py
───────────────────
Centralised configuration — reads from environment / .env file.
All defaults are safe for local development.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from pydantic import field_validator

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────
    APP_NAME:    str = "BlockShield"
    APP_VERSION: str = "1.0.0"
    DEBUG:       bool = False
    LOG_LEVEL:   str = "INFO"
    LOG_JSON:    bool = False
    WORKERS:     int = 4

    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./blockshield.db"
    DB_ECHO:      bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ── Auth / JWT ────────────────────────────────────────────
    JWT_SECRET_KEY:           str = "CHANGE_ME_IN_PRODUCTION_32chars!!"
    JWT_ALGORITHM:            str = "HS256"
    ACCESS_TOKEN_EXPIRE_MIN:  int = 30
    REFRESH_TOKEN_EXPIRE_H:   int = 24
    api_key:                  str = ""
    API_KEYS:                 str = ""       # comma-separated legacy API keys

    @property
    def valid_api_keys(self) -> set[str]:
        return set(k.strip() for k in self.API_KEYS.split(",") if k.strip())

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL:     str  = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = False
    RATE_LIMIT_RPM: int = 60

    # ── Broker ───────────────────────────────────────────────
    BROKER_BACKEND:           Literal["memory", "redis", "kafka"] = "memory"
    KAFKA_BOOTSTRAP_SERVERS:  str = "localhost:9092"
    KAFKA_CONSUMER_GROUP:     str = "blockshield-consumers"
    KAFKA_AUTO_OFFSET_RESET:  str = "latest"

    # ── ML / Models ───────────────────────────────────────────
    MODEL_DIR:          str = "models"
    MODEL_PATH:         str = "models/isolation_forest.joblib"
    ANOMALY_THRESHOLD:  float = 0.65
    RETRAIN_THRESHOLD:  int = 50
    RETRAIN_INTERVAL_SEC: int = 3600
    MAX_TRAINING_ROWS:  int = 100_000
    GNN_MODEL_PATH:     str = "models/wallet_gnn.pt"
    OFAC_SDN_CSV:       str = "data/sdn_advanced.csv"

    # ── Chain RPC ─────────────────────────────────────────────
    ETH_ALCHEMY_KEY:     str = "yGKzYO3sCb0pIOYI7mPRl"
    ETH_INFURA_KEY:      str = ""
    ETH_RPC_URL:         str = ""
    POLYGON_ALCHEMY_KEY: str = "bjWnEfH0EcO--Iw7kEgC2"
    POLYGON_RPC_URL:     str = "https://polygon-rpc.com"
    BSC_RPC_URL:         str = "https://bsc-dataseed.binance.org"
    ARBITRUM_ALCHEMY_KEY: str = "https://arb-mainnet.g.alchemy.com/v2/bjWnEfH0EcO--Iw7kEgC2"
    ENABLED_CHAINS:      str = "ethereum"  # comma-separated

    @property
    def enabled_chains_list(self) -> list[str]:
        return [c.strip() for c in self.ENABLED_CHAINS.split(",") if c.strip()]

    # ── Webhook Alerting ──────────────────────────────────────
    webhook_enabled: bool = False
    webhook_url:     str = ""

    # ── CORS ──────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Convenience singleton
settings = get_settings()
