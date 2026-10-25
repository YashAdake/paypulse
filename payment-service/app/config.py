from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All config comes from env vars (case-insensitive); defaults suit local compose."""

    database_url: str = "postgresql://paypulse:paypulse@localhost:5432/paypulse"
    db_pool_min_size: int = Field(default=1, ge=1)
    db_pool_max_size: int = Field(default=10, ge=1)
    db_connect_timeout_s: int = Field(default=5, ge=1)
    # How long a request waits for a free pooled connection before we answer 503.
    db_pool_timeout_s: float = Field(default=5.0, gt=0)
    db_statement_timeout_ms: int = Field(default=5000, ge=100)
    # Postgres usually wins the race thanks to compose healthchecks; this covers restarts.
    db_startup_retries: int = Field(default=30, ge=1)
    db_startup_retry_delay_s: float = Field(default=2.0, gt=0)

    traffic_rps: float = Field(default=20.0, ge=0, le=100)
    log_level: str = "INFO"
