import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.admin import router as admin_router
from app.api.v1.agent_config import router as agent_config_router
from app.api.v1.chat import router as chat_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.documents import router as documents_router
from app.api.v1.escalations import router as escalations_router
from app.api.v1.health import router as health_router
from app.api.v1.review_queue import router as review_queue_router
from app.api.v1.voice import router as voice_router
from app.api.v1.voice_config import router as voice_config_router
from app.config import settings
from app.metrics import setup_metrics
from app.middleware.pii import PIIRedactionMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.services.redis_client import close_redis
from app.telemetry import setup_telemetry

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="ConvoAI",
    description="Conversational AI Customer Service Platform",
    version="1.0.0",
)

setup_metrics(app)
setup_telemetry(app)


@app.on_event("shutdown")
async def _shutdown() -> None:
    await close_redis()


# --- Middleware (outermost first) ---
# PIIRedactionMiddleware is a raw ASGI middleware — must wrap via add_middleware
# with the class directly; FastAPI calls __init__(app) automatically.
app.add_middleware(PIIRedactionMiddleware)
app.add_middleware(RateLimitMiddleware)

_cors_origins = (
    ["*"]
    if settings.app_env == "development" or settings.cors_origins == "*"
    else [o.strip() for o in settings.cors_origins.split(",")]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(health_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(escalations_router, prefix="/api/v1")
app.include_router(agent_config_router, prefix="/api/v1")
app.include_router(review_queue_router, prefix="/api/v1")
app.include_router(voice_router, prefix="/api/v1")
app.include_router(voice_config_router, prefix="/api/v1")
