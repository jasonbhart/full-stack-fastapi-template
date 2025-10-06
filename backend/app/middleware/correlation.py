"""Correlation ID middleware for request tracing.

This middleware:
- Generates or extracts correlation IDs from incoming requests
- Propagates correlation IDs through the request lifecycle
- Adds correlation IDs to response headers
- Integrates with structured logging
- Integrates with Langfuse trace IDs when available
"""

import logging
import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core import logging as app_logging
from app.core.telemetry import get_current_trace

logger = logging.getLogger(__name__)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation IDs to requests and responses.

    This middleware:
    1. Checks for existing correlation ID in request headers (X-Correlation-ID)
    2. Generates a new correlation ID if none exists
    3. Sets the correlation ID in the logging context
    4. Integrates with Langfuse trace IDs if available
    5. Adds correlation ID to response headers
    6. Cleans up context after request completes
    """

    CORRELATION_ID_HEADER = "X-Correlation-ID"
    TRACE_ID_HEADER = "X-Trace-ID"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process the request and add correlation ID.

        Args:
            request: The incoming request
            call_next: The next middleware or endpoint handler

        Returns:
            The response with correlation ID header
        """
        # Get or generate correlation ID
        correlation_id = request.headers.get(
            self.CORRELATION_ID_HEADER, str(uuid.uuid4())
        )

        # Set correlation ID in logging context
        app_logging.set_correlation_id(correlation_id)

        # Try to get and set Langfuse trace ID if available
        trace = get_current_trace()
        if trace is not None:
            try:
                trace_id = trace.id
                app_logging.set_trace_id(trace_id)
            except Exception as e:
                logger.debug(f"Failed to get trace ID from Langfuse: {e}")

        # Log request with correlation ID
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else "unknown",
            },
        )

        try:
            # Process request
            response = await call_next(request)

            # Add correlation ID to response headers
            response.headers[self.CORRELATION_ID_HEADER] = correlation_id

            # Add trace ID to response headers if available
            trace_id = app_logging.get_trace_id()
            if trace_id:
                response.headers[self.TRACE_ID_HEADER] = trace_id

            # Log response
            logger.info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
            )

            return response

        except Exception as e:
            # Log error with correlation ID
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {str(e)}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

        finally:
            # Clean up context to prevent leakage between requests
            app_logging.clear_context()
