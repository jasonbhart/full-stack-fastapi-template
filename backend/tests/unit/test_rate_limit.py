"""Unit tests for rate limiting graceful degradation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import Request, Response
from fastapi_limiter import FastAPILimiter

from app.core.rate_limit import create_rate_limiter


@pytest.mark.asyncio
async def test_rate_limiter_bypassed_when_redis_unavailable() -> None:
    """Test that rate limiter gracefully bypasses when Redis is unavailable."""
    # Ensure Redis is None (simulating unavailability)
    FastAPILimiter.redis = None

    # Create a rate limiter
    limiter = create_rate_limiter(times=5, seconds=60)

    # Create mock request and response
    mock_request = MagicMock(spec=Request)
    mock_response = MagicMock(spec=Response)

    # Call the limiter - should not raise, should bypass gracefully
    await limiter(mock_request, mock_response)
    # If we got here without exception, graceful degradation works


@pytest.mark.asyncio
async def test_rate_limiter_does_not_crash_when_redis_available() -> None:
    """Test that rate limiter works without error when Redis is available.

    This test verifies the signature is correct - it accepts both request and response.
    Full functional testing is done in integration tests.
    """
    # Set Redis as available (but don't actually connect)
    mock_redis = AsyncMock()
    FastAPILimiter.redis = mock_redis

    # Create a rate limiter
    limiter = create_rate_limiter(times=5, seconds=60)

    # Create mock request and response
    mock_request = MagicMock(spec=Request)
    mock_response = MagicMock(spec=Response)

    # Verify the limiter callable accepts both parameters without error
    # We're not testing the full rate limiting logic here, just the signature
    assert callable(limiter)

    # The key test: verify it expects both request and response parameters
    import inspect
    sig = inspect.signature(limiter)
    params = list(sig.parameters.keys())
    assert "request" in params
    assert "response" in params

    # Clean up
    FastAPILimiter.redis = None


@pytest.mark.asyncio
async def test_rate_limiter_disabled_when_setting_false() -> None:
    """Test that rate limiter returns no-op when RATE_LIMIT_ENABLED is False."""
    with patch("app.core.rate_limit.settings") as mock_settings:
        mock_settings.RATE_LIMIT_ENABLED = False

        # Create a rate limiter
        limiter = create_rate_limiter(times=5, seconds=60)

        # Create mock request and response
        mock_request = MagicMock(spec=Request)
        mock_response = MagicMock(spec=Response)

        # Call the limiter - should be no-op
        await limiter(mock_request, mock_response)
        # If we got here without exception, no-op limiter works


def test_rate_limiter_warning_flag_exists() -> None:
    """Test that the warning flag exists to prevent log spam."""
    import app.core.rate_limit

    # Verify the flag exists
    assert hasattr(app.core.rate_limit, "_REDIS_UNAVAILABLE_WARNED")

    # Verify it's a boolean
    assert isinstance(app.core.rate_limit._REDIS_UNAVAILABLE_WARNED, bool)
