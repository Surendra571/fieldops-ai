import json

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General
    PROJECT_NAME: str = "FieldOps AI"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "fieldops_dev"
    MONGODB_MIN_POOL_SIZE: int = 10
    MONGODB_MAX_POOL_SIZE: int = 50
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = 5000

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Integration Providers ("mock" by default for deterministic local dev/tests)
    NOTIFICATION_PROVIDER: str = "mock"
    MAPS_PROVIDER: str = "mock"
    CALENDAR_PROVIDER: str = "mock"
    CRM_PROVIDER: str = "mock"
    VOICE_STT_PROVIDER: str = "mock"
    VOICE_TTS_PROVIDER: str = "mock"
    LLM_PROVIDER: str = "mock"

    # LLM & Voice Credentials (optional for live providers; mock by default)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_VOICE_MODEL: str = "whisper-1"
    OPENAI_TTS_VOICE: str = "alloy"

    # Agent Session & Safeguards
    CONVERSATION_HISTORY_LIMIT: int = 20
    AGENT_TIMEOUT_SECONDS: float = 15.0
    AGENT_MAX_REPAIR_ATTEMPTS: int = 3
    PROMPT_INJECTION_STRICT_MODE: bool = True

    # Webhooks & Security
    WEBHOOK_SIGNING_SECRET: str = "dev-webhook-secret-signing-key-32chars"
    WEBHOOK_TOLERANCE_SECONDS: int = 300  # 5 minutes replay protection

    # Optional Real Provider Credentials (never committed)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "notifications@fieldops.ai"

    # Transactional Outbox & Worker Settings
    OUTBOX_MAX_RETRIES: int = 5
    OUTBOX_BASE_BACKOFF_SECONDS: float = 2.0
    OUTBOX_MAX_BACKOFF_SECONDS: float = 300.0
    OUTBOX_BATCH_SIZE: int = 50

    # Operational & Observability
    LOG_FORMAT: str = "text"  # "text" or "json"
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 120
    REQUEST_TIMEOUT_SECONDS: float = 30.0

    # Security & Auth
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production-minimum-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # CORS
    CORS_ORIGINS: list[str] | str = Field(
        default=["http://localhost:3000", "http://localhost:5173"]
    )

    # Seed Credentials
    SEED_ADMIN_EMAIL: str = "admin@fieldops.ai"
    SEED_ADMIN_PASSWORD: str = "AdminSecurePassword123!"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            if v.lower() in ("true", "1", "yes", "on", "dev", "development"):
                return True
            return False
        return bool(v)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        raise ValueError("Invalid format for CORS_ORIGINS")

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_production_secrets(cls, v: str, info) -> str:
        env = info.data.get("ENVIRONMENT", "development")
        if env == "production":
            if "dev-secret" in v or len(v) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be a secure random key with at least 32 characters in production."
                )
        return v


settings = Settings()
