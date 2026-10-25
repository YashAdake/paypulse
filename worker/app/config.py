from pydantic import Field
from pydantic_settings import BaseSettings

from app.contracts import WorkflowSettings


class Settings(BaseSettings):
    """All config comes from env vars (case-insensitive); defaults suit local compose."""

    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    task_queue: str = "paypulse"
    temporal_connect_retries: int = Field(default=30, ge=1)
    temporal_connect_retry_delay_s: float = Field(default=2.0, gt=0)

    payment_service_url: str = "http://localhost:8080"
    http_timeout_s: float = Field(default=5.0, gt=0)

    # Detector: open an incident when a bank+method group drops below the threshold.
    detector_interval_s: float = Field(default=5.0, gt=0)
    detector_window_s: int = Field(default=60, ge=10)
    detector_min_success_rate: float = Field(default=0.90, gt=0, le=1)
    detector_min_payments: int = Field(default=20, ge=1)
    # Wait this long after an incident closes before opening another for the same bank.
    detector_cooldown_s: float = Field(default=120.0, ge=0)

    # LLM: any OpenAI-compatible endpoint (Jarvislabs Token Factory by default).
    llm_base_url: str = "https://models.jarvislabs.net/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-v4.1-flash-1017"
    llm_timeout_s: float = Field(default=60.0, gt=0)
    # Generous: this model spends hidden reasoning tokens before the JSON answer.
    llm_max_tokens: int = Field(default=1500, ge=200)

    supermemory_base_url: str = "https://api.supermemory.ai"
    supermemory_api_key: str = ""
    supermemory_container_tag: str = "paypulse-incidents"
    supermemory_threshold: float = Field(default=0.3, ge=0, le=1)

    approval_timeout_s: int = Field(default=900, ge=30)
    # Where `python -m app.seed_memory` reads past postmortems from (mounted in compose).
    seed_dir: str = "/seed"
    log_level: str = "INFO"

    def workflow_settings(self) -> WorkflowSettings:
        return WorkflowSettings(approval_timeout_s=self.approval_timeout_s)
