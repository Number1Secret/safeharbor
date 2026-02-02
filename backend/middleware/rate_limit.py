"""
Rate Limiting Middleware

Redis-backed sliding window rate limiter.
General endpoints: 100 req/min per IP.
Auth endpoints: 10 req/min per IP.
"""

import time

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from backend.config import get_settings

settings = get_settings()

# Rate limit defaults
GENERAL_LIMIT = 100  # requests per minute
AUTH_LIMIT = 10  # requests per minute for auth endpoints
WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter using Redis."""

    def __init__(self, app):
        super().__init__(app)
        self._redis = None

    async def _get_redis(self):
        """Lazy-init Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                )
            except Exception:
                # If Redis is unavailable, skip rate limiting
                return None
        return self._redis

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip rate limiting for health checks
        if request.url.path.startswith("/health"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Determine rate limit
        is_auth = "/auth/" in path or path.endswith("/auth")
        limit = AUTH_LIMIT if is_auth else GENERAL_LIMIT
        prefix = "rl:auth" if is_auth else "rl:general"
        key = f"{prefix}:{client_ip}"

        redis = await self._get_redis()
        if redis is None:
            # No Redis — allow request but don't rate limit
            return await call_next(request)

        try:
            now = time.time()
            window_start = now - WINDOW_SECONDS

            pipe = redis.pipeline()
            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            # Count current entries
            pipe.zcard(key)
            # Add this request
            pipe.zadd(key, {str(now): now})
            # Set expiry on the key
            pipe.expire(key, WINDOW_SECONDS + 1)
            results = await pipe.execute()

            request_count = results[1]

            if request_count >= limit:
                retry_after = int(WINDOW_SECONDS - (now - window_start))
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(max(retry_after, 1))},
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(max(0, limit - request_count - 1))
            return response

        except HTTPException:
            raise
        except Exception:
            # If Redis errors out, allow the request
            return await call_next(request)
