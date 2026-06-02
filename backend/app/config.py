from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://convoai:convoai@localhost:5432/convoai"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # OpenAI
    openai_api_key: str

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # RAG
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    chunk_size: int = 512
    chunk_overlap: int = 64
    retrieval_top_k: int = 5
    retrieval_fetch_k: int = 20
    mmr_lambda: float = 0.5
    escalation_confidence_threshold: float = 0.65

    # LangChain Agent
    llm_model: str = "gpt-4-turbo"   # OQ-01: swap to gpt-4o after benchmark
    llm_temperature: float = 0.0
    agent_max_iterations: int = 5

    # Memory
    memory_window: int = 10  # last N turns kept in Redis context window

    # Auth
    api_key: str = "dev-api-key"          # override in production
    jwt_secret: str = "dev-jwt-secret"    # override in production
    jwt_algorithm: str = "HS256"

    # Rate limiting
    rate_limit_rpm: int = 100             # requests per minute per IP

    # CORS (comma-separated origins for production)
    cors_origins: str = "*"

    # PII redaction (Phase 7)
    pii_redaction: bool = False   # set PII_REDACTION=true to activate

    # Escalation ticketing (OQ-07)
    # Set ESCALATION_WEBHOOK_URL to activate; leave empty for log-only mode
    escalation_webhook_url: str = ""
    escalation_webhook_secret: str = ""  # HMAC-SHA256 signing secret (optional)

    # Voice — Whisper STT
    # OQ-03: "openai" uses OpenAI hosted API; "sidecar" uses self-hosted faster-whisper
    whisper_backend: str = "openai"
    whisper_sidecar_url: str = "http://whisper-stt:9000"

    # Voice — ElevenLabs TTS
    elevenlabs_api_key: str = ""                      # required for TTS; empty = TTS disabled
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM" # "Rachel" — default ElevenLabs voice
    elevenlabs_model: str = "eleven_turbo_v2_5"        # lowest-latency model
    elevenlabs_speed: float = 1.0


settings = Settings()
