"""Tests for evaluation module."""

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.evaluation.evaluator import Evaluator


@pytest.fixture
def mock_settings() -> Generator[MagicMock, None, None]:
    """Mock settings to avoid requiring real API keys."""
    with patch("app.evaluation.evaluator.settings") as mock:
        mock.EVALUATION_API_KEY = "test-key"
        mock.EVALUATION_BASE_URL = "https://api.openai.com/v1"
        mock.EVALUATION_LLM = "gpt-4o-mini"
        mock.EVALUATION_SLEEP_TIME = 0
        mock.LANGFUSE_PUBLIC_KEY = "pk-test"
        mock.LANGFUSE_SECRET_KEY = "sk-test"
        mock.LANGFUSE_HOST = "https://cloud.langfuse.com"
        yield mock


@pytest.fixture
def mock_openai() -> Generator[MagicMock, None, None]:
    """Mock OpenAI client."""
    with patch("app.evaluation.evaluator.openai.AsyncOpenAI") as mock:
        yield mock


@pytest.fixture
def mock_langfuse() -> Generator[MagicMock, None, None]:
    """Mock Langfuse client."""
    with patch("app.evaluation.evaluator.Langfuse") as mock:
        yield mock


def test_evaluator_initialization(mock_settings: MagicMock, mock_openai: MagicMock, mock_langfuse: MagicMock) -> None:
    """Test that Evaluator initializes with correct configuration."""
    evaluator = Evaluator()

    # Verify OpenAI client initialized with correct settings
    mock_openai.assert_called_once_with(
        api_key=mock_settings.EVALUATION_API_KEY,
        base_url=mock_settings.EVALUATION_BASE_URL,
    )

    # Verify Langfuse client initialized with host parameter
    mock_langfuse.assert_called_once_with(
        public_key=mock_settings.LANGFUSE_PUBLIC_KEY,
        secret_key=mock_settings.LANGFUSE_SECRET_KEY,
        host=mock_settings.LANGFUSE_HOST,
    )


def test_report_saves_to_writable_location(
    mock_settings: MagicMock, mock_openai: MagicMock, mock_langfuse: MagicMock, tmp_path: Path
) -> None:
    """Test that reports are saved to current working directory, not package directory."""
    evaluator = Evaluator()
    evaluator.report = {
        "timestamp": "2025-01-01T00:00:00",
        "model": "test-model",
        "total_traces": 0,
        "successful_traces": 0,
        "failed_traces": 0,
        "duration_seconds": 0,
        "metrics_summary": {},
        "successful_traces_details": [],
        "failed_traces_details": [],
    }

    # Change to temp directory to avoid polluting the project
    import os

    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        # Save report
        report_path = evaluator._save_report()

        # Verify report is in the temp directory, not the package directory
        assert Path(report_path).parent.parent == tmp_path
        assert Path(report_path).parent.name == "reports"
        assert Path(report_path).exists()

        # Verify report contents
        with open(report_path) as f:
            saved_report = json.load(f)
            assert saved_report["model"] == "test-model"

        # Verify report_path is set in the in-memory report object
        assert evaluator.report["report_path"] == report_path

    finally:
        os.chdir(original_cwd)
