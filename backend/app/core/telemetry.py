"""Telemetry and observability module with Langfuse integration and Prometheus metrics.

This module provides distributed tracing capabilities using Langfuse,
with support for lazy initialization, sampling controls, and graceful
handling of missing API keys or dependencies.

It also provides Prometheus metrics for monitoring agent operations and API performance.
"""

import asyncio
import logging
import random
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, AsyncIterator, Iterator

from app.core.config import settings

# Conditional import for Prometheus (optional dependency)
try:
    from prometheus_client import Counter, Gauge, Histogram, Info

    PROMETHEUS_AVAILABLE: bool = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Create no-op placeholders
    if not TYPE_CHECKING:
        Counter = None  # type: ignore[assignment,misc]
        Gauge = None  # type: ignore[assignment,misc]
        Histogram = None  # type: ignore[assignment,misc]
        Info = None  # type: ignore[assignment,misc]

# Conditional import for Langfuse (optional dependency)
if TYPE_CHECKING:
    from langfuse import Langfuse
    from langfuse.client import StatefulSpanClient, StatefulTraceClient  # type: ignore[import-not-found]

# Track availability at runtime
try:
    from langfuse import Langfuse
    from langfuse.client import StatefulSpanClient, StatefulTraceClient

    LANGFUSE_AVAILABLE: bool = True
except ImportError:
    if not TYPE_CHECKING:
        Langfuse = None  # type: ignore[assignment,misc]
        StatefulSpanClient = None  # type: ignore[assignment,misc]
        StatefulTraceClient = None  # type: ignore[assignment,misc]
    LANGFUSE_AVAILABLE = False

logger = logging.getLogger(__name__)

# Context variables for trace propagation across async operations
_current_trace: ContextVar[Any] = ContextVar("_current_trace", default=None)
_current_span: ContextVar[Any] = ContextVar("_current_span", default=None)

# Singleton Langfuse client instance (lazy initialized)
_langfuse_client: "Langfuse | None" = None


# ============================================================================
# Prometheus Metrics
# ============================================================================

# Agent operation metrics (following Prometheus naming conventions)
# Counter for total agent invocations
agent_invocations_total: Any = None
# Counter for agent invocations by status (completed, failed, timeout)
agent_invocations_by_status_total: Any = None
# Histogram for agent execution latency in seconds
agent_execution_duration_seconds: Any = None
# Gauge for currently running agents
agent_active_executions: Any = None
# Counter for total tokens used (prompt + completion)
agent_tokens_total: Any = None
# Histogram for agent prompt token count
agent_prompt_tokens: Any = None
# Histogram for agent completion token count
agent_completion_tokens: Any = None
# Info metric for application metadata
app_info: Any = None


def _initialize_prometheus_metrics() -> None:
    """Initialize Prometheus metrics for agent operations.

    This function creates all custom metrics following Prometheus naming conventions:
    - Use lowercase with underscores
    - Use base unit (seconds, bytes, etc.)
    - Suffix with unit name
    - Use _total suffix for counters
    """
    global agent_invocations_total
    global agent_invocations_by_status_total
    global agent_execution_duration_seconds
    global agent_active_executions
    global agent_tokens_total
    global agent_prompt_tokens
    global agent_completion_tokens
    global app_info

    if not PROMETHEUS_AVAILABLE:
        logger.warning(
            "Prometheus metrics disabled: prometheus-client package not installed. "
            "Install it with: pip install prometheus-fastapi-instrumentator"
        )
        return

    try:
        # Total agent invocations counter
        agent_invocations_total = Counter(
            "agent_invocations_total",
            "Total number of agent invocations",
            ["agent_type"],
        )

        # Agent invocations by status
        agent_invocations_by_status_total = Counter(
            "agent_invocations_by_status_total",
            "Total number of agent invocations by final status",
            ["status", "agent_type"],
        )

        # Agent execution duration histogram
        agent_execution_duration_seconds = Histogram(
            "agent_execution_duration_seconds",
            "Agent execution duration in seconds",
            ["agent_type"],
            buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, float("inf")),
        )

        # Currently active agent executions
        agent_active_executions = Gauge(
            "agent_active_executions",
            "Number of currently executing agents",
            ["agent_type"],
        )

        # Total tokens used (prompt + completion)
        agent_tokens_total = Counter(
            "agent_tokens_total",
            "Total tokens used by agents",
            ["token_type", "agent_type"],
        )

        # Prompt tokens histogram
        agent_prompt_tokens = Histogram(
            "agent_prompt_tokens",
            "Number of prompt tokens per agent invocation",
            ["agent_type"],
            buckets=(50, 100, 250, 500, 1000, 2500, 5000, 10000, float("inf")),
        )

        # Completion tokens histogram
        agent_completion_tokens = Histogram(
            "agent_completion_tokens",
            "Number of completion tokens per agent invocation",
            ["agent_type"],
            buckets=(50, 100, 250, 500, 1000, 2500, 5000, 10000, float("inf")),
        )

        # Application info
        app_info = Info(
            "app",
            "Application version and environment information",
        )
        app_info.info(
            {
                "version": "0.1.0",
                "environment": settings.ENVIRONMENT,
                "app_env": settings.APP_ENV.value,
            }
        )

        logger.info("Prometheus metrics initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Prometheus metrics: {e}")


def record_agent_invocation(
    agent_type: str = "default",
) -> None:
    """Record an agent invocation.

    Args:
        agent_type: Type/name of the agent being invoked

    Note:
        User-specific tracking should be done via traces or logs, not Prometheus labels.
        Labels must have low cardinality to avoid overwhelming the TSDB.
    """
    if agent_invocations_total is not None:
        try:
            agent_invocations_total.labels(agent_type=agent_type).inc()
        except Exception as e:
            logger.error(f"Failed to record agent invocation: {e}")


def record_agent_status(
    status: str,
    agent_type: str = "default",
) -> None:
    """Record the final status of an agent execution.

    Args:
        status: Final status (completed, failed, timeout, etc.)
        agent_type: Type/name of the agent
    """
    if agent_invocations_by_status_total is not None:
        try:
            agent_invocations_by_status_total.labels(
                status=status, agent_type=agent_type
            ).inc()
        except Exception as e:
            logger.error(f"Failed to record agent status: {e}")


def record_agent_duration(
    duration_seconds: float,
    agent_type: str = "default",
) -> None:
    """Record the execution duration of an agent.

    Args:
        duration_seconds: Duration in seconds
        agent_type: Type/name of the agent
    """
    if agent_execution_duration_seconds is not None:
        try:
            agent_execution_duration_seconds.labels(agent_type=agent_type).observe(
                duration_seconds
            )
        except Exception as e:
            logger.error(f"Failed to record agent duration: {e}")


def record_agent_tokens(
    prompt_tokens: int,
    completion_tokens: int,
    agent_type: str = "default",
) -> None:
    """Record token usage for an agent execution.

    Args:
        prompt_tokens: Number of prompt tokens used
        completion_tokens: Number of completion tokens used
        agent_type: Type/name of the agent
    """
    if agent_tokens_total is not None:
        try:
            agent_tokens_total.labels(
                token_type="prompt", agent_type=agent_type
            ).inc(prompt_tokens)
            agent_tokens_total.labels(
                token_type="completion", agent_type=agent_type
            ).inc(completion_tokens)
        except Exception as e:
            logger.error(f"Failed to record agent tokens (counter): {e}")

    if agent_prompt_tokens is not None:
        try:
            agent_prompt_tokens.labels(agent_type=agent_type).observe(prompt_tokens)
        except Exception as e:
            logger.error(f"Failed to record prompt tokens (histogram): {e}")

    if agent_completion_tokens is not None:
        try:
            agent_completion_tokens.labels(agent_type=agent_type).observe(
                completion_tokens
            )
        except Exception as e:
            logger.error(f"Failed to record completion tokens (histogram): {e}")


@contextmanager
def track_agent_execution(agent_type: str = "default") -> Iterator[None]:
    """Context manager to track active agent executions.

    This increments the active executions gauge on entry and decrements on exit.

    Args:
        agent_type: Type/name of the agent

    Example:
        with track_agent_execution("langgraph"):
            # Agent execution code here
            pass
    """
    if agent_active_executions is not None:
        try:
            agent_active_executions.labels(agent_type=agent_type).inc()
        except Exception as e:
            logger.error(f"Failed to increment active executions: {e}")

    try:
        yield
    finally:
        if agent_active_executions is not None:
            try:
                agent_active_executions.labels(agent_type=agent_type).dec()
            except Exception as e:
                logger.error(f"Failed to decrement active executions: {e}")


def _should_sample() -> bool:
    """Determine if the current request should be sampled based on configured sample rate.

    Returns:
        True if the request should be traced, False otherwise.
    """
    if not settings.LANGFUSE_ENABLED:
        return False

    # Sample rate of 1.0 means trace everything, 0.0 means trace nothing
    sample_rate = max(0.0, min(1.0, settings.LANGFUSE_SAMPLE_RATE))
    return random.random() < sample_rate


def _get_langfuse_client() -> "Langfuse | None":
    """Get or create the Langfuse client instance with lazy initialization.

    This function handles:
    - Lazy initialization (client created on first use)
    - Missing API keys (returns None gracefully)
    - Missing langfuse package (returns None gracefully)
    - Global singleton pattern to reuse the client

    Returns:
        Langfuse client instance or None if disabled/unavailable.
    """
    global _langfuse_client

    # Return early if Langfuse is disabled
    if not settings.LANGFUSE_ENABLED:
        return None

    # Return early if langfuse package is not available
    if not LANGFUSE_AVAILABLE or Langfuse is None:
        logger.warning(
            "Langfuse is enabled but the langfuse package is not installed. "
            "Install it with: pip install langfuse"
        )
        return None

    # Return existing client if already initialized
    if _langfuse_client is not None:
        return _langfuse_client

    # Check for required API keys
    if not settings.LANGFUSE_SECRET_KEY or not settings.LANGFUSE_PUBLIC_KEY:
        logger.warning(
            "Langfuse is enabled but API keys are not configured. "
            "Set LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY environment variables."
        )
        return None

    # Initialize the client
    try:
        _langfuse_client = Langfuse(
            secret_key=settings.LANGFUSE_SECRET_KEY,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            host=settings.LANGFUSE_HOST,
        )
        logger.info(
            f"Langfuse client initialized successfully (host: {settings.LANGFUSE_HOST}, "
            f"sample_rate: {settings.LANGFUSE_SAMPLE_RATE})"
        )
        return _langfuse_client
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse client: {e}")
        return None


def get_current_trace() -> "StatefulTraceClient | None":
    """Get the current trace from context.

    Returns:
        Current trace instance or None if no trace is active.
    """
    return _current_trace.get()


def get_current_span() -> "StatefulSpanClient | None":
    """Get the current span from context.

    Returns:
        Current span instance or None if no span is active.
    """
    return _current_span.get()


@contextmanager
def trace(
    name: str,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    **kwargs: Any,
) -> Iterator["StatefulTraceClient | None"]:
    """Create a new Langfuse trace with context management.

    This context manager:
    - Creates a trace if sampling allows and Langfuse is configured
    - Sets the trace in the context for nested operations
    - Automatically finalizes the trace on exit
    - Handles errors gracefully

    Args:
        name: Name of the trace
        user_id: Optional user ID to associate with the trace
        metadata: Optional metadata dictionary
        tags: Optional list of tags
        **kwargs: Additional arguments to pass to Langfuse trace creation

    Yields:
        Langfuse trace instance or None if tracing is disabled/unavailable.

    Example:
        with trace("agent_execution", user_id="user123") as t:
            # Your code here
            pass
    """
    client = _get_langfuse_client()

    # Return None if client is unavailable or sampling rejects this trace
    if client is None or not _should_sample():
        yield None
        return

    trace_obj = None
    token = None
    try:
        # Create the trace
        trace_obj = client.trace(  # type: ignore[attr-defined]
            name=name,
            user_id=user_id,
            metadata=metadata,
            tags=tags,
            **kwargs,
        )

        # Set trace in context for nested operations
        token = _current_trace.set(trace_obj)
        yield trace_obj
    except Exception as e:
        logger.error(f"Error in trace '{name}': {e}")
        # Mark trace with error status if available
        if trace_obj is not None:
            try:
                trace_obj.update(metadata={"error": str(e), "status": "error"})
            except Exception:
                pass
        raise
    finally:
        # Reset context before finalizing
        if token is not None:
            _current_trace.reset(token)

        # End the trace and flush to ensure it's sent to Langfuse
        if trace_obj is not None:
            try:
                trace_obj.end()
                client.flush()
            except Exception as e:
                logger.error(f"Error finalizing trace '{name}': {e}")


@asynccontextmanager
async def async_trace(
    name: str,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    **kwargs: Any,
) -> AsyncIterator["StatefulTraceClient | None"]:
    """Create a new Langfuse trace with async context management.

    This async context manager provides the same functionality as trace()
    but for async contexts, maintaining trace context across async operations.

    Note: Langfuse operations are run in a thread executor to avoid blocking
    the event loop with synchronous HTTP calls.

    Args:
        name: Name of the trace
        user_id: Optional user ID to associate with the trace
        metadata: Optional metadata dictionary
        tags: Optional list of tags
        **kwargs: Additional arguments to pass to Langfuse trace creation

    Yields:
        Langfuse trace instance or None if tracing is disabled/unavailable.

    Example:
        async with async_trace("agent_execution", user_id="user123") as t:
            # Your async code here
            await some_operation()
    """
    client = _get_langfuse_client()

    # Return None if client is unavailable or sampling rejects this trace
    if client is None or not _should_sample():
        yield None
        return

    trace_obj = None
    token = None
    try:
        # Create the trace (run in thread executor to avoid blocking event loop)
        trace_obj = await asyncio.to_thread(
            client.trace,  # type: ignore[attr-defined]
            name=name,
            user_id=user_id,
            metadata=metadata,
            tags=tags,
            **kwargs,
        )

        # Set trace in context for nested operations
        token = _current_trace.set(trace_obj)
        yield trace_obj
    except Exception as e:
        logger.error(f"Error in async trace '{name}': {e}")
        # Mark trace with error status if available
        if trace_obj is not None:
            try:
                await asyncio.to_thread(
                    trace_obj.update,
                    metadata={"error": str(e), "status": "error"}
                )
            except Exception:
                pass
        raise
    finally:
        # Reset context before finalizing
        if token is not None:
            _current_trace.reset(token)

        # End the trace and flush to ensure it's sent to Langfuse
        # (run in thread executor to avoid blocking event loop)
        if trace_obj is not None:
            try:
                await asyncio.to_thread(trace_obj.end)
                await asyncio.to_thread(client.flush)
            except Exception as e:
                logger.error(f"Error finalizing async trace '{name}': {e}")


@contextmanager
def span(
    name: str,
    metadata: dict[str, Any] | None = None,
    input_data: Any = None,
    **kwargs: Any,
) -> Iterator["StatefulSpanClient | None"]:
    """Create a new span within the current trace.

    This context manager:
    - Creates a span within the current trace context
    - Sets the span in context for nested operations
    - Automatically finalizes the span on exit
    - Returns None gracefully if no trace is active

    Args:
        name: Name of the span
        metadata: Optional metadata dictionary
        input_data: Optional input data for the span
        **kwargs: Additional arguments to pass to Langfuse span creation

    Yields:
        Langfuse span instance or None if no trace is active.

    Example:
        with trace("agent_execution") as t:
            with span("tool_execution", metadata={"tool": "calculator"}) as s:
                # Your code here
                pass
    """
    current_trace = get_current_trace()

    # Return None if no trace is active
    if current_trace is None:
        yield None
        return

    span_obj = None
    token = None
    try:
        # Create the span
        span_obj = current_trace.span(
            name=name,
            metadata=metadata,
            input=input_data,
            **kwargs,
        )

        # Set span in context for nested operations
        token = _current_span.set(span_obj)
        yield span_obj
    except Exception as e:
        logger.error(f"Error in span '{name}': {e}")
        # Mark span with error status if available
        if span_obj is not None:
            try:
                span_obj.update(metadata={"error": str(e), "status": "error"})
            except Exception:
                pass
        raise
    finally:
        # Reset context before finalizing
        if token is not None:
            _current_span.reset(token)

        # End the span to finalize it
        if span_obj is not None:
            try:
                span_obj.end()
            except Exception as e:
                logger.error(f"Error finalizing span '{name}': {e}")


@asynccontextmanager
async def async_span(
    name: str,
    metadata: dict[str, Any] | None = None,
    input_data: Any = None,
    **kwargs: Any,
) -> AsyncIterator["StatefulSpanClient | None"]:
    """Create a new span within the current trace (async version).

    This async context manager provides the same functionality as span()
    but for async contexts, maintaining span context across async operations.

    Note: Langfuse operations are run in a thread executor to avoid blocking
    the event loop with synchronous HTTP calls.

    Args:
        name: Name of the span
        metadata: Optional metadata dictionary
        input_data: Optional input data for the span
        **kwargs: Additional arguments to pass to Langfuse span creation

    Yields:
        Langfuse span instance or None if no trace is active.

    Example:
        async with async_trace("agent_execution") as t:
            async with async_span("tool_execution", metadata={"tool": "calculator"}) as s:
                # Your async code here
                await some_operation()
    """
    current_trace = get_current_trace()

    # Return None if no trace is active
    if current_trace is None:
        yield None
        return

    span_obj = None
    token = None
    try:
        # Create the span (run in thread executor to avoid blocking event loop)
        span_obj = await asyncio.to_thread(
            current_trace.span,
            name=name,
            metadata=metadata,
            input=input_data,
            **kwargs,
        )

        # Set span in context for nested operations
        token = _current_span.set(span_obj)
        yield span_obj
    except Exception as e:
        logger.error(f"Error in async span '{name}': {e}")
        # Mark span with error status if available
        if span_obj is not None:
            try:
                await asyncio.to_thread(
                    span_obj.update,
                    metadata={"error": str(e), "status": "error"}
                )
            except Exception:
                pass
        raise
    finally:
        # Reset context before finalizing
        if token is not None:
            _current_span.reset(token)

        # End the span to finalize it
        # (run in thread executor to avoid blocking event loop)
        if span_obj is not None:
            try:
                await asyncio.to_thread(span_obj.end)
            except Exception as e:
                logger.error(f"Error finalizing async span '{name}': {e}")


def flush_telemetry() -> None:
    """Flush all pending telemetry data to Langfuse.

    This should be called before application shutdown to ensure
    all traces are sent to Langfuse.
    """
    client = _get_langfuse_client()
    if client is not None:
        try:
            client.flush()
            logger.info("Langfuse telemetry data flushed successfully")
        except Exception as e:
            logger.error(f"Error flushing Langfuse telemetry: {e}")


def shutdown_telemetry() -> None:
    """Shutdown the telemetry system and cleanup resources.

    This should be called during application shutdown to properly
    close the Langfuse client and flush any pending data.
    """
    global _langfuse_client

    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
            logger.info("Langfuse client shutdown successfully")
        except Exception as e:
            logger.error(f"Error shutting down Langfuse client: {e}")
        finally:
            _langfuse_client = None
