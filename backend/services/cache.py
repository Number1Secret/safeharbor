"""
Redis Cache Service

Provides a caching layer for frequently accessed data.
TTL-based with key prefixing and JSON serialization.
"""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from backend.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Lazy-initialized connection pool
_redis: aioredis.Redis | None = None

# TTL defaults (seconds)
TTL_ORG = 300  # 5 minutes for org data
TTL_EMPLOYEE_LIST = 60  # 1 minute for employee lists
TTL_CALCULATION = 120  # 2 minutes for calculation data
TTL_SHORT = 30  # 30 seconds for fast-changing data


async def _get_redis() -> aioredis.Redis:
    """Get or create Redis connection."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
        )
    return _redis


async def get_cached(key: str) -> Any | None:
    """
    Get a cached value by key.

    Returns None if key doesn't exist or Redis is unavailable.
    """
    try:
        r = await _get_redis()
        data = await r.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.debug(f"Cache miss (error): {key} — {e}")
        return None


async def set_cached(key: str, value: Any, ttl: int = TTL_SHORT) -> bool:
    """
    Set a cached value with TTL.

    Returns True if cached successfully, False on error.
    """
    try:
        r = await _get_redis()
        await r.set(key, json.dumps(value, default=str), ex=ttl)
        return True
    except Exception as e:
        logger.debug(f"Cache set failed: {key} — {e}")
        return False


async def invalidate(key: str) -> bool:
    """Delete a cached key."""
    try:
        r = await _get_redis()
        await r.delete(key)
        return True
    except Exception as e:
        logger.debug(f"Cache invalidate failed: {key} — {e}")
        return False


async def invalidate_pattern(pattern: str) -> int:
    """
    Delete all keys matching a pattern.

    Uses SCAN to avoid blocking Redis on large keyspaces.
    Returns number of keys deleted.
    """
    try:
        r = await _get_redis()
        count = 0
        async for key in r.scan_iter(match=pattern, count=100):
            await r.delete(key)
            count += 1
        return count
    except Exception as e:
        logger.debug(f"Cache pattern invalidate failed: {pattern} — {e}")
        return 0


# ── Key Builders ──────────────────────────────────────


def org_key(org_id: str) -> str:
    """Cache key for organization data."""
    return f"org:{org_id}"


def employee_list_key(org_id: str) -> str:
    """Cache key for employee list."""
    return f"employees:{org_id}"


def employee_key(org_id: str, employee_id: str) -> str:
    """Cache key for a single employee."""
    return f"employee:{org_id}:{employee_id}"


def calc_run_key(org_id: str, run_id: str) -> str:
    """Cache key for a calculation run."""
    return f"calc:{org_id}:{run_id}"


def integration_list_key(org_id: str) -> str:
    """Cache key for integration list."""
    return f"integrations:{org_id}"
