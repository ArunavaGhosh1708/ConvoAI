"""Redis sliding-window rate limiter (Starlette middleware)."""

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.services.redis_client import get_redis

logger = logging.getLogger(__name__)

# Paths exempt from rate limiting
_EXEMPT = {"/api/v1/health"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window counter per client IP.
    Allows `rate_limit_rpm` requests per 60-second window.
    Uses Redis sorted sets: score = timestamp, member = timestamp string.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _EXEMPT:
            return await call_next(request)

        redis = await get_redis()
        ip = request.client.host if request.client else "unknown"
        key = f"convoai:rate:{ip}"
        now = time.time()
        window_start = now - 60.0

        try:
            async with redis.pipeline(transaction=False) as pipe:
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {f"{now:.6f}": now})
                pipe.zcard(key)
                pipe.expire(key, 60)
                results = await pipe.execute()
            count = results[2]
        except Exception:
            logger.exception("Rate limiter Redis error — allowing request")
            return await call_next(request)

        if count > settings.rate_limit_rpm:
            logger.warning("Rate limit exceeded: ip=%s count=%d", ip, count)
            return Response(
                content='{"detail":"Rate limit exceeded. Max 100 requests/minute."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"},
            )

        return await call_next(request)
