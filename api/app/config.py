from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All config comes from env vars (case-insensitive); defaults suit local compose."""

    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_connect_retries: int = Field(default=30, ge=1)
    temporal_connect_retry_delay_s: float = Field(default=2.0, gt=0)
    temporal_rpc_timeout_s: float = Field(default=5.0, gt=0)

    payment_service_url: str = "http://localhost:8080"
    http_timeout_s: float = Field(default=5.0, gt=0)

    # Only used to show which partner integrations are switched on; never sent anywhere.
    llm_api_key: str = ""
    llm_model: str = "deepseek-v4.1-flash-1017"
    supermemory_api_key: str = ""

    log_level: str = "INFO"
