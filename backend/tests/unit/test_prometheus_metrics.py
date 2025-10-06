"""Unit tests for Prometheus metrics integration."""

from unittest.mock import MagicMock, patch

import pytest

from app.core import telemetry


class TestPrometheusMetricsInitialization:
    """Test Prometheus metrics initialization."""

    def test_metrics_initialization_when_available(self) -> None:
        """Test that metrics initialize correctly when Prometheus is available."""
        with patch("app.core.telemetry.PROMETHEUS_AVAILABLE", True):
            with patch("app.core.telemetry.Counter") as mock_counter:
                with patch("app.core.telemetry.Gauge") as mock_gauge:
                    with patch("app.core.telemetry.Histogram") as mock_histogram:
                        with patch("app.core.telemetry.Info") as mock_info:
                            # Reset metrics to None
                            telemetry.agent_invocations_total = None
                            telemetry.agent_active_executions = None

                            # Initialize metrics
                            telemetry._initialize_prometheus_metrics()

                            # Verify counters were created
                            assert mock_counter.call_count >= 2
                            # Verify gauges were created
                            assert mock_gauge.call_count >= 1
                            # Verify histograms were created
                            assert mock_histogram.call_count >= 3
                            # Verify info was created
                            assert mock_info.call_count >= 1

    def test_metrics_initialization_when_unavailable(self) -> None:
        """Test that metrics initialization handles missing Prometheus gracefully."""
        with patch("app.core.telemetry.PROMETHEUS_AVAILABLE", False):
            # Should not raise an exception
            telemetry._initialize_prometheus_metrics()


class TestAgentMetricRecording:
    """Test agent metric recording functions."""

    def test_record_agent_invocation(self) -> None:
        """Test recording agent invocations."""
        mock_metric = MagicMock()
        with patch.object(telemetry, "agent_invocations_total", mock_metric):
            telemetry.record_agent_invocation(agent_type="langgraph")
            mock_metric.labels.assert_called_once_with(agent_type="langgraph")
            mock_metric.labels.return_value.inc.assert_called_once()

    def test_record_agent_invocation_when_metric_none(self) -> None:
        """Test recording when metric is None doesn't raise error."""
        with patch.object(telemetry, "agent_invocations_total", None):
            # Should not raise an exception
            telemetry.record_agent_invocation(agent_type="default")

    def test_record_agent_status(self) -> None:
        """Test recording agent execution status."""
        mock_metric = MagicMock()
        with patch.object(telemetry, "agent_invocations_by_status_total", mock_metric):
            telemetry.record_agent_status(status="completed", agent_type="langgraph")
            mock_metric.labels.assert_called_once_with(
                status="completed", agent_type="langgraph"
            )
            mock_metric.labels.return_value.inc.assert_called_once()

    def test_record_agent_duration(self) -> None:
        """Test recording agent execution duration."""
        mock_metric = MagicMock()
        with patch.object(telemetry, "agent_execution_duration_seconds", mock_metric):
            telemetry.record_agent_duration(duration_seconds=2.5, agent_type="langgraph")
            mock_metric.labels.assert_called_once_with(agent_type="langgraph")
            mock_metric.labels.return_value.observe.assert_called_once_with(2.5)

    def test_record_agent_tokens(self) -> None:
        """Test recording agent token usage."""
        mock_total = MagicMock()
        mock_prompt_hist = MagicMock()
        mock_completion_hist = MagicMock()

        with patch.object(telemetry, "agent_tokens_total", mock_total):
            with patch.object(telemetry, "agent_prompt_tokens", mock_prompt_hist):
                with patch.object(telemetry, "agent_completion_tokens", mock_completion_hist):
                    telemetry.record_agent_tokens(
                        prompt_tokens=100,
                        completion_tokens=50,
                        agent_type="langgraph"
                    )

                    # Verify counter was incremented for both token types
                    assert mock_total.labels.call_count == 2

                    # Verify histograms were updated
                    mock_prompt_hist.labels.assert_called_once_with(agent_type="langgraph")
                    mock_prompt_hist.labels.return_value.observe.assert_called_once_with(100)

                    mock_completion_hist.labels.assert_called_once_with(agent_type="langgraph")
                    mock_completion_hist.labels.return_value.observe.assert_called_once_with(50)


class TestAgentExecutionTracking:
    """Test agent execution tracking context manager."""

    def test_track_agent_execution_increments_and_decrements(self) -> None:
        """Test that active executions gauge is incremented and decremented."""
        mock_metric = MagicMock()

        with patch.object(telemetry, "agent_active_executions", mock_metric):
            with telemetry.track_agent_execution(agent_type="langgraph"):
                # Inside context, should be incremented
                mock_metric.labels.assert_called_with(agent_type="langgraph")
                mock_metric.labels.return_value.inc.assert_called_once()

            # After context, should be decremented
            assert mock_metric.labels.return_value.dec.call_count == 1

    def test_track_agent_execution_when_metric_none(self) -> None:
        """Test tracking when metric is None doesn't raise error."""
        with patch.object(telemetry, "agent_active_executions", None):
            # Should not raise an exception
            with telemetry.track_agent_execution():
                pass

    def test_track_agent_execution_decrements_on_error(self) -> None:
        """Test that gauge is decremented even when code raises exception."""
        mock_metric = MagicMock()

        with patch.object(telemetry, "agent_active_executions", mock_metric):
            with pytest.raises(ValueError):
                with telemetry.track_agent_execution(agent_type="langgraph"):
                    raise ValueError("Test error")

            # Should still be decremented after exception
            assert mock_metric.labels.return_value.dec.call_count == 1
