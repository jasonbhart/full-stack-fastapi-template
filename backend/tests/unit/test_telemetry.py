"""Unit tests for the telemetry module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.core import telemetry


class TestTelemetrySampling:
    """Test sampling logic."""

    def test_should_sample_disabled(self) -> None:
        """Test that sampling returns False when Langfuse is disabled."""
        with patch("app.core.telemetry.settings") as mock_settings:
            mock_settings.LANGFUSE_ENABLED = False
            mock_settings.LANGFUSE_SAMPLE_RATE = 1.0
            assert telemetry._should_sample() is False

    def test_should_sample_always(self) -> None:
        """Test that sampling returns True with rate 1.0."""
        with patch("app.core.telemetry.settings") as mock_settings:
            mock_settings.LANGFUSE_ENABLED = True
            mock_settings.LANGFUSE_SAMPLE_RATE = 1.0
            assert telemetry._should_sample() is True

    def test_should_sample_never(self) -> None:
        """Test that sampling returns False with rate 0.0."""
        with patch("app.core.telemetry.settings") as mock_settings:
            mock_settings.LANGFUSE_ENABLED = True
            mock_settings.LANGFUSE_SAMPLE_RATE = 0.0
            assert telemetry._should_sample() is False

    def test_should_sample_clamps_rate(self) -> None:
        """Test that sample rate is clamped between 0 and 1."""
        with patch("app.core.telemetry.settings") as mock_settings:
            mock_settings.LANGFUSE_ENABLED = True

            # Test clamping above 1.0
            mock_settings.LANGFUSE_SAMPLE_RATE = 2.0
            with patch("app.core.telemetry.random.random", return_value=0.5):
                assert telemetry._should_sample() is True

            # Test clamping below 0.0
            mock_settings.LANGFUSE_SAMPLE_RATE = -1.0
            with patch("app.core.telemetry.random.random", return_value=0.5):
                assert telemetry._should_sample() is False


class TestLangfuseClient:
    """Test Langfuse client initialization."""

    def test_client_returns_none_when_disabled(self) -> None:
        """Test that client returns None when Langfuse is disabled."""
        with patch("app.core.telemetry.settings") as mock_settings:
            mock_settings.LANGFUSE_ENABLED = False
            with patch("app.core.telemetry._langfuse_client", None):
                client = telemetry._get_langfuse_client()
                assert client is None

    def test_client_returns_none_when_not_available(self) -> None:
        """Test that client returns None when langfuse package is not available."""
        with patch("app.core.telemetry.settings") as mock_settings:
            mock_settings.LANGFUSE_ENABLED = True
            with patch("app.core.telemetry.LANGFUSE_AVAILABLE", False):
                with patch("app.core.telemetry._langfuse_client", None):
                    client = telemetry._get_langfuse_client()
                    assert client is None

    def test_client_returns_none_with_missing_keys(self) -> None:
        """Test that client returns None when API keys are missing."""
        with patch("app.core.telemetry.settings") as mock_settings:
            mock_settings.LANGFUSE_ENABLED = True
            mock_settings.LANGFUSE_SECRET_KEY = None
            mock_settings.LANGFUSE_PUBLIC_KEY = None
            with patch("app.core.telemetry.LANGFUSE_AVAILABLE", True):
                with patch("app.core.telemetry._langfuse_client", None):
                    client = telemetry._get_langfuse_client()
                    assert client is None

    def test_client_initializes_with_valid_config(self) -> None:
        """Test that client initializes correctly with valid configuration."""
        mock_langfuse = MagicMock()
        with patch("app.core.telemetry.settings") as mock_settings:
            mock_settings.LANGFUSE_ENABLED = True
            mock_settings.LANGFUSE_SECRET_KEY = "test_secret"
            mock_settings.LANGFUSE_PUBLIC_KEY = "test_public"
            mock_settings.LANGFUSE_HOST = "https://test.langfuse.com"
            with patch("app.core.telemetry.LANGFUSE_AVAILABLE", True):
                with patch("app.core.telemetry.Langfuse", return_value=mock_langfuse):
                    with patch("app.core.telemetry._langfuse_client", None):
                        client = telemetry._get_langfuse_client()
                        assert client == mock_langfuse


class TestTraceContext:
    """Test trace context management."""

    def test_trace_returns_none_when_disabled(self) -> None:
        """Test that trace returns None when Langfuse is disabled."""
        with patch("app.core.telemetry._get_langfuse_client", return_value=None):
            with telemetry.trace("test_trace") as t:
                assert t is None

    def test_trace_returns_none_when_not_sampled(self) -> None:
        """Test that trace returns None when sampling rejects it."""
        mock_client = MagicMock()
        with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
            with patch("app.core.telemetry._should_sample", return_value=False):
                with telemetry.trace("test_trace") as t:
                    assert t is None

    def test_trace_creates_trace_when_enabled(self) -> None:
        """Test that trace creates a trace object when enabled and sampled."""
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_client.trace.return_value = mock_trace

        with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
            with patch("app.core.telemetry._should_sample", return_value=True):
                with telemetry.trace("test_trace", user_id="user123") as t:
                    assert t == mock_trace
                    mock_client.trace.assert_called_once_with(
                        name="test_trace",
                        user_id="user123",
                        metadata=None,
                        tags=None,
                    )

    def test_trace_sets_context(self) -> None:
        """Test that trace sets the trace in context."""
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_client.trace.return_value = mock_trace

        with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
            with patch("app.core.telemetry._should_sample", return_value=True):
                with telemetry.trace("test_trace") as t:
                    # Inside the trace context, current trace should be set
                    assert telemetry.get_current_trace() == mock_trace

                # Outside the trace context, current trace should be None
                assert telemetry.get_current_trace() is None

    def test_trace_ends_and_flushes_on_exit(self) -> None:
        """Test that trace ends and flushes data on exit."""
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_client.trace.return_value = mock_trace

        with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
            with patch("app.core.telemetry._should_sample", return_value=True):
                with telemetry.trace("test_trace") as t:
                    pass

                # Verify both end() and flush() are called
                mock_trace.end.assert_called_once()
                mock_client.flush.assert_called_once()

    def test_trace_ends_on_error(self) -> None:
        """Test that trace ends even when an error occurs."""
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_client.trace.return_value = mock_trace

        with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
            with patch("app.core.telemetry._should_sample", return_value=True):
                try:
                    with telemetry.trace("test_trace") as t:
                        raise ValueError("Test error")
                except ValueError:
                    pass

                # Verify trace is ended and marked with error
                mock_trace.update.assert_called_once()
                mock_trace.end.assert_called_once()
                mock_client.flush.assert_called_once()


class TestSpanContext:
    """Test span context management."""

    def test_span_returns_none_without_trace(self) -> None:
        """Test that span returns None when no trace is active."""
        with telemetry.span("test_span") as s:
            assert s is None

    def test_span_creates_span_within_trace(self) -> None:
        """Test that span creates a span within an active trace."""
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_span = MagicMock()
        mock_client.trace.return_value = mock_trace
        mock_trace.span.return_value = mock_span

        with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
            with patch("app.core.telemetry._should_sample", return_value=True):
                with telemetry.trace("test_trace") as t:
                    with telemetry.span("test_span", metadata={"key": "value"}) as s:
                        assert s == mock_span
                        mock_trace.span.assert_called_once_with(
                            name="test_span",
                            metadata={"key": "value"},
                            input=None,
                        )

    def test_span_sets_context(self) -> None:
        """Test that span sets the span in context."""
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_span = MagicMock()
        mock_client.trace.return_value = mock_trace
        mock_trace.span.return_value = mock_span

        with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
            with patch("app.core.telemetry._should_sample", return_value=True):
                with telemetry.trace("test_trace"):
                    with telemetry.span("test_span") as s:
                        # Inside the span context, current span should be set
                        assert telemetry.get_current_span() == mock_span

                    # Outside the span context, current span should be None
                    assert telemetry.get_current_span() is None

    def test_span_ends_on_exit(self) -> None:
        """Test that span ends on exit."""
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_span = MagicMock()
        mock_client.trace.return_value = mock_trace
        mock_trace.span.return_value = mock_span

        with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
            with patch("app.core.telemetry._should_sample", return_value=True):
                with telemetry.trace("test_trace"):
                    with telemetry.span("test_span") as s:
                        pass

                    # Verify span.end() is called
                    mock_span.end.assert_called_once()

    def test_span_ends_on_error(self) -> None:
        """Test that span ends even when an error occurs."""
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_span = MagicMock()
        mock_client.trace.return_value = mock_trace
        mock_trace.span.return_value = mock_span

        with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
            with patch("app.core.telemetry._should_sample", return_value=True):
                with telemetry.trace("test_trace"):
                    try:
                        with telemetry.span("test_span") as s:
                            raise ValueError("Test error")
                    except ValueError:
                        pass

                    # Verify span is ended and marked with error
                    mock_span.update.assert_called_once()
                    mock_span.end.assert_called_once()


class TestTelemetryLifecycle:
    """Test telemetry lifecycle management."""

    def test_flush_telemetry_calls_client_flush(self) -> None:
        """Test that flush_telemetry calls client.flush()."""
        mock_client = MagicMock()

        with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
            telemetry.flush_telemetry()
            mock_client.flush.assert_called_once()

    def test_flush_telemetry_handles_none_client(self) -> None:
        """Test that flush_telemetry handles None client gracefully."""
        with patch("app.core.telemetry._get_langfuse_client", return_value=None):
            # Should not raise an exception
            telemetry.flush_telemetry()

    def test_shutdown_telemetry_flushes_and_clears_client(self) -> None:
        """Test that shutdown_telemetry flushes and clears the client."""
        mock_client = MagicMock()

        with patch("app.core.telemetry._langfuse_client", mock_client):
            telemetry.shutdown_telemetry()
            mock_client.flush.assert_called_once()
            assert telemetry._langfuse_client is None


class TestAsyncTraceContext:
    """Test async trace context management."""

    def test_async_trace_returns_none_when_disabled(self) -> None:
        """Test that async_trace returns None when Langfuse is disabled."""
        import asyncio

        async def run_test() -> None:
            with patch("app.core.telemetry._get_langfuse_client", return_value=None):
                async with telemetry.async_trace("test_trace") as t:
                    assert t is None

        asyncio.run(run_test())

    def test_async_trace_creates_trace_when_enabled(self) -> None:
        """Test that async_trace creates a trace object when enabled."""
        import asyncio

        async def run_test() -> None:
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_client.trace.return_value = mock_trace

            with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
                with patch("app.core.telemetry._should_sample", return_value=True):
                    with patch("asyncio.to_thread", side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)):
                        async with telemetry.async_trace("test_trace", user_id="user123") as t:
                            pass

            # Verify trace was created and ended
            mock_client.trace.assert_called_once()
            mock_trace.end.assert_called_once()

        asyncio.run(run_test())

    def test_async_trace_uses_thread_executor(self) -> None:
        """Test that async_trace runs Langfuse operations in thread executor."""
        import asyncio

        async def run_test() -> None:
            mock_client = MagicMock()
            mock_trace = MagicMock()

            with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
                with patch("app.core.telemetry._should_sample", return_value=True):
                    with patch("asyncio.to_thread", side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)) as mock_to_thread:
                        async with telemetry.async_trace("test_trace") as t:
                            pass

                        # Verify asyncio.to_thread was called for trace creation, end, and flush
                        assert mock_to_thread.call_count >= 2  # At least trace.end() and client.flush()

        asyncio.run(run_test())

    def test_async_trace_ends_on_error(self) -> None:
        """Test that async_trace ends even when an error occurs."""
        import asyncio

        async def run_test() -> None:
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_client.trace.return_value = mock_trace

            with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
                with patch("app.core.telemetry._should_sample", return_value=True):
                    with patch("asyncio.to_thread", side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)):
                        try:
                            async with telemetry.async_trace("test_trace") as t:
                                raise ValueError("Test error")
                        except ValueError:
                            pass

            # Verify trace is ended and marked with error
            mock_trace.update.assert_called_once()
            mock_trace.end.assert_called_once()

        asyncio.run(run_test())


class TestAsyncSpanContext:
    """Test async span context management."""

    def test_async_span_returns_none_without_trace(self) -> None:
        """Test that async_span returns None when no trace is active."""
        import asyncio

        async def run_test() -> None:
            async with telemetry.async_span("test_span") as s:
                assert s is None

        asyncio.run(run_test())

    def test_async_span_creates_span_within_trace(self) -> None:
        """Test that async_span creates a span within an active trace."""
        import asyncio

        async def run_test() -> None:
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_span = MagicMock()
            mock_client.trace.return_value = mock_trace
            mock_trace.span.return_value = mock_span

            with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
                with patch("app.core.telemetry._should_sample", return_value=True):
                    with patch("asyncio.to_thread", side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)):
                        async with telemetry.async_trace("test_trace"):
                            async with telemetry.async_span("test_span", metadata={"key": "value"}) as s:
                                pass

            # Verify span was created and ended
            mock_trace.span.assert_called_once()
            mock_span.end.assert_called_once()

        asyncio.run(run_test())

    def test_async_span_uses_thread_executor(self) -> None:
        """Test that async_span runs Langfuse operations in thread executor."""
        import asyncio

        async def run_test() -> None:
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_span = MagicMock()

            with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
                with patch("app.core.telemetry._should_sample", return_value=True):
                    with patch("asyncio.to_thread", side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)) as mock_to_thread:
                        async with telemetry.async_trace("test_trace"):
                            async with telemetry.async_span("test_span") as s:
                                pass

                        # Verify asyncio.to_thread was called for span operations
                        # Should be called for: trace creation, trace end, trace flush, span creation, span end
                        assert mock_to_thread.call_count >= 4

        asyncio.run(run_test())

    def test_async_span_ends_on_error(self) -> None:
        """Test that async_span ends even when an error occurs."""
        import asyncio

        async def run_test() -> None:
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_span = MagicMock()
            mock_client.trace.return_value = mock_trace
            mock_trace.span.return_value = mock_span

            with patch("app.core.telemetry._get_langfuse_client", return_value=mock_client):
                with patch("app.core.telemetry._should_sample", return_value=True):
                    with patch("asyncio.to_thread", side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)):
                        async with telemetry.async_trace("test_trace"):
                            try:
                                async with telemetry.async_span("test_span") as s:
                                    raise ValueError("Test error")
                            except ValueError:
                                pass

            # Verify span is ended and marked with error
            mock_span.update.assert_called_once()
            mock_span.end.assert_called_once()

        asyncio.run(run_test())
