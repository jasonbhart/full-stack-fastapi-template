"""Rate limiting configuration and utilities using FastAPI-Limiter with Redis backend.

This module provides:
- FastAPI-Limiter initialization with Redis
- Rate limit decorators for agent endpoints
- Resilient Redis connection handling
- Automatic rate limit header injection (via FastAPI-Limiter)
"""

import logging
from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Track whether we've already warned about Redis unavailability
# This prevents log spam during outages (one warning per process lifecycle)
_REDIS_UNAVAILABLE_WARNED = False


async def init_rate_limiter() -> None:
    """Initialize FastAPI-Limiter with Redis backend.

    This function:
    - Connects to Redis using configuration settings
    - Initializes FastAPI-Limiter for rate limiting
    - Handles connection errors gracefully
    - Logs initialization status

    Raises:
        Exception: If Redis connection fails and rate limiting is enabled
    """
    if not settings.RATE_LIMIT_ENABLED:
        logger.info("Rate limiting is disabled in configuration")
        return

    try:
        # Create Redis connection with timeout and retry settings
        redis_client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )

        # Test the connection
        await redis_client.ping()

        # Initialize FastAPI-Limiter
        await FastAPILimiter.init(redis_client)

        logger.info(
            f"Rate limiter initialized successfully with Redis at "
            f"{settings.REDIS_HOST}:{settings.REDIS_PORT}"
        )
    except (RedisConnectionError, RedisTimeoutError) as e:
        logger.error(f"Failed to connect to Redis for rate limiting: {e}")
        if settings.RATE_LIMIT_ENABLED:
            logger.warning(
                "Rate limiting is enabled but Redis is unavailable. "
                "Endpoints will not be rate limited until Redis is available."
            )
        raise
    except Exception as e:
        logger.error(f"Failed to initialize rate limiter: {e}")
        raise


async def close_rate_limiter() -> None:
    """Close FastAPI-Limiter and Redis connection gracefully.

    This function should be called during application shutdown to:
    - Close Redis connections properly
    - Clean up rate limiter resources
    """
    if not settings.RATE_LIMIT_ENABLED:
        return

    try:
        await FastAPILimiter.close()
        logger.info("Rate limiter closed successfully")
    except Exception as e:
        logger.error(f"Error closing rate limiter: {e}")


def create_rate_limiter(
    times: int,
    seconds: int,
    identifier: Callable[[Request], str] | None = None,
) -> Callable[[Request, Response], Awaitable[None]]:
    """Create a rate limiter dependency for FastAPI endpoints.

    This factory function creates a RateLimiter dependency that can be
    used with FastAPI's dependency injection system. The returned dependency
    checks at request time whether FastAPILimiter is initialized, ensuring
    graceful degradation when Redis is unavailable.

    Args:
        times: Number of requests allowed
        seconds: Time window in seconds
        identifier: Optional function to identify the client (defaults to IP-based)

    Returns:
        RateLimiter dependency for FastAPI endpoints (or no-op if disabled/unavailable)

    Example:
        @router.post("/endpoint")
        async def endpoint(
            rate_limit: Annotated[None, Depends(create_rate_limiter(5, 60))]
        ):
            ...
    """
    # No-op dependency when rate limiting is disabled in config
    async def no_op_limiter(request: Request, response: Response) -> None:
        return None

    if not settings.RATE_LIMIT_ENABLED:
        return no_op_limiter

    # Default identifier uses route template + user ID or IP
    # This ensures each endpoint has its own independent rate limit counter
    async def default_identifier(request: Request) -> str:
        # Get base identifier (user ID or IP)
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "id"):
            base = f"user:{user.id}"
        else:
            # Fallback to IP address
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                base = f"ip:{forwarded.split(',')[0].strip()}"
            else:
                client_host = request.client.host if request.client else "unknown"
                base = f"ip:{client_host}"

        # Use route template (not concrete path) to prevent evasion via path params
        # E.g., /api/v1/agent/runs/{run_id} instead of /api/v1/agent/runs/123
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        return f"{route_path}:{base}"

    identifier_func = identifier or default_identifier

    # Create the actual RateLimiter instance
    # FastAPI-Limiter automatically adds standard rate limit headers:
    # X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
    actual_limiter = RateLimiter(
        times=times,
        seconds=seconds,
        identifier=identifier_func,
    )

    # Wrapper that checks if FastAPILimiter is initialized at request time
    async def resilient_limiter(request: Request, response: Response) -> None:
        global _REDIS_UNAVAILABLE_WARNED

        # Check if FastAPILimiter was successfully initialized
        if FastAPILimiter.redis is None:
            # Redis unavailable - log warning once to avoid log spam during outages
            if not _REDIS_UNAVAILABLE_WARNED:
                logger.warning(
                    "Rate limiting bypassed: FastAPILimiter not initialized (Redis unavailable). "
                    "This warning will only be shown once per process."
                )
                _REDIS_UNAVAILABLE_WARNED = True
            return None

        # Redis available - reset warning flag and apply rate limiting
        _REDIS_UNAVAILABLE_WARNED = False
        # RateLimiter expects only request when called manually
        # The signature shows (request, response) but response is actually a call_next callable
        # when used as middleware. Passing Response instance causes runtime errors.
        await actual_limiter(request)  # type: ignore[call-arg]
        return None

    return resilient_limiter


# Pre-configured rate limiters for common use cases
agent_run_limiter = create_rate_limiter(
    times=settings.RATE_LIMIT_PER_MINUTE,
    seconds=60,
)

agent_history_limiter = create_rate_limiter(
    times=settings.RATE_LIMIT_PER_MINUTE * 2,  # Allow more reads than writes
    seconds=60,
)

agent_evaluation_limiter = create_rate_limiter(
    times=settings.RATE_LIMIT_PER_MINUTE,
    seconds=60,
)
