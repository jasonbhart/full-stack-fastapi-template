"""Structured logging configuration with JSON formatting and correlation ID support.

This module provides:
- Environment-specific log levels (local: DEBUG, staging: INFO, production: WARNING)
- JSON formatting for production environments
- Integration with correlation IDs from middleware
- Integration with Langfuse trace IDs from telemetry
- Structured log context management
"""

import logging
import sys
from contextvars import ContextVar
from typing import Any, Union

from pythonjsonlogger.jsonlogger import JsonFormatter  # type: ignore[attr-defined]

from app.core.config import AppEnv, settings

# Context variables for correlation and trace IDs
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


class CorrelationIDFilter(logging.Filter):
    """Add correlation ID and trace ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id and trace_id to the log record.

        Args:
            record: The log record to modify

        Returns:
            Always True to allow the record to be logged
        """
        setattr(record, "correlation_id", _correlation_id.get() or "none")
        setattr(record, "trace_id", _trace_id.get() or "none")
        return True


class CustomJSONFormatter(JsonFormatter):
    """Custom JSON formatter with correlation and trace ID support."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """Add custom fields to JSON log records.

        Args:
            log_record: The dictionary that will be serialized to JSON
            record: The original log record
            message_dict: Dictionary from the message
        """
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record["timestamp"] = self.formatTime(record, self.datefmt)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["module"] = record.module
        log_record["function"] = record.funcName
        log_record["line"] = record.lineno

        # Add correlation and trace IDs
        log_record["correlation_id"] = getattr(record, "correlation_id", "none")
        log_record["trace_id"] = getattr(record, "trace_id", "none")

        # Add process and thread info
        log_record["process"] = record.process
        log_record["thread"] = record.thread

        # Add environment context
        log_record["environment"] = settings.APP_ENV.value


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter for local development."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors for console output.

        Args:
            record: The log record to format

        Returns:
            Formatted log string with colors
        """
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = (
                f"{self.BOLD}{self.COLORS[levelname]}{levelname}{self.RESET}"
            )

        # Format the message
        formatted = super().format(record)

        # Add correlation and trace IDs if present
        correlation_id = getattr(record, "correlation_id", None)
        trace_id = getattr(record, "trace_id", None)

        extra_info = []
        if correlation_id and correlation_id != "none":
            extra_info.append(f"correlation_id={correlation_id}")
        if trace_id and trace_id != "none":
            extra_info.append(f"trace_id={trace_id}")

        if extra_info:
            formatted = f"{formatted} [{' '.join(extra_info)}]"

        return formatted


def get_log_level() -> int:
    """Get the log level based on the current environment.

    Returns:
        Logging level constant (DEBUG, INFO, WARNING, etc.)
    """
    env_to_level = {
        AppEnv.LOCAL: logging.DEBUG,
        AppEnv.STAGING: logging.INFO,
        AppEnv.PRODUCTION: logging.WARNING,
    }
    return env_to_level.get(settings.APP_ENV, logging.INFO)


def setup_logging() -> None:
    """Configure structured logging for the application.

    This function:
    - Sets up JSON formatting for production
    - Configures colored console output for local development
    - Adds correlation ID filter to all handlers
    - Sets environment-specific log levels
    """
    # Get the root logger
    root_logger = logging.getLogger()

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Set log level based on environment
    log_level = get_log_level()
    root_logger.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Choose formatter based on environment
    formatter: Union[CustomJSONFormatter, ColoredConsoleFormatter]
    if settings.APP_ENV == AppEnv.PRODUCTION:
        # JSON formatter for production
        formatter = CustomJSONFormatter(
            "%(timestamp)s %(level)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        # Colored console formatter for local/staging
        formatter = ColoredConsoleFormatter(
            fmt=(
                "%(asctime)s - %(levelname)s - %(name)s - "
                "%(module)s:%(funcName)s:%(lineno)d - %(message)s"
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)

    # Add correlation ID filter
    correlation_filter = CorrelationIDFilter()
    console_handler.addFilter(correlation_filter)

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    # Configure third-party loggers
    # Reduce noise from uvicorn
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    # Reduce noise from sqlalchemy
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Reduce noise from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.info(
        f"Logging configured for {settings.APP_ENV.value} environment "
        f"with level {logging.getLevelName(log_level)}"
    )


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current context.

    Args:
        correlation_id: The correlation ID to set
    """
    _correlation_id.set(correlation_id)


def get_correlation_id() -> str | None:
    """Get the correlation ID for the current context.

    Returns:
        The current correlation ID or None
    """
    return _correlation_id.get()


def set_trace_id(trace_id: str | None) -> None:
    """Set the Langfuse trace ID for the current context.

    Args:
        trace_id: The trace ID to set, or None to clear
    """
    _trace_id.set(trace_id)


def get_trace_id() -> str | None:
    """Get the Langfuse trace ID for the current context.

    Returns:
        The current trace ID or None
    """
    return _trace_id.get()


def clear_context() -> None:
    """Clear correlation and trace IDs from the current context.

    This should be called at the end of each request to prevent
    context leakage between requests.
    """
    _correlation_id.set(None)
    _trace_id.set(None)


# Create a default logger instance for modules that need it
logger = logging.getLogger(__name__)
