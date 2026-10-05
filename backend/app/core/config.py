from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime configuration. Every secret comes from the environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = "Middly Interoperability Platform"
    environment: str = "development"
    demo_mode: bool = True
    log_level: str = "INFO"

    # --- Database / infra
    database_url: str = "postgresql+psycopg://middly:middly@localhost:5432/middly"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/%2F"

    # --- OIDC / Keycloak
    oidc_issuer: str = "http://localhost:8080/realms/middly"
    oidc_jwks_url: str = "http://localhost:8080/realms/middly/protocol/openid-connect/certs"
    oidc_audience: str = "middly-api"
    # Static JWKS (JSON string). Used by automated tests instead of fetching from Keycloak.
    oidc_static_jwks: str | None = None

    # --- HTTP
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    rate_limit_per_minute: int = 240

    # --- Plugins / configuration directories
    connectors_path: str = str(_REPO_ROOT / "connectors")
    workflow_config_path: str = str(_REPO_ROOT / "workflow-engine")

    # --- Events
    # "rabbitmq" publishes through the broker; "inline" dispatches handlers in-process
    # (used by the seeder and automated tests).
    event_dispatch_mode: str = "rabbitmq"
    events_exchange: str = "middly.events"
    events_dlx: str = "middly.dlx"

    # --- Connector resilience defaults
    connector_timeout_seconds: float = 3.0
    connector_max_retries: int = 2
    connector_backoff_base_seconds: float = 0.25
    circuit_failure_threshold: int = 3
    circuit_open_seconds: int = 30
    stale_data_days: int = 365

    # --- Worker
    auto_retry_interval_seconds: int = 90
    auto_retry_max_attempts: int = 5
    outbox_relay_interval_seconds: int = 5
    health_check_interval_seconds: int = 30
    worker_metrics_port: int = 9100

    mock_admin_key: str = "change-me-mock-admin-key"


@lru_cache
def get_settings() -> Settings:
    return Settings()
