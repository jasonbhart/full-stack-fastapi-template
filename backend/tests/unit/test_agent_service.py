"""Unit tests for agent service orchestration layer.

This module tests the AgentService class with mocked external dependencies:
- LangGraph agent invocation
- Langfuse tracing
- Database persistence

All tests use mocks to ensure isolation and fast execution.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlmodel import Session

from app.agents.service import AgentService, create_agent_service
from app.models import User


@pytest.fixture
def mock_user() -> User:
    """Create a mock user for testing."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        full_name="Test User",
        hashed_password="hashedpassword",
        is_active=True,
        is_superuser=False,
    )
    return user


@pytest.fixture
def mock_session() -> Mock:
    """Create a mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def agent_service(mock_session: Mock) -> AgentService:
    """Create an AgentService instance with mocked session."""
    return AgentService(session=mock_session)


class TestCreateLangfuseHandler:
    """Test Langfuse handler creation with various configurations."""

    @patch("app.agents.service.settings")
    def test_handler_created_when_enabled_and_configured(
        self,
        mock_settings: Mock,
        agent_service: AgentService,
    ) -> None:
        """Test handler is created when Langfuse is enabled and properly configured."""
        # Configure mock settings
        mock_settings.LANGFUSE_ENABLED = True
        mock_settings.LANGFUSE_SECRET_KEY = "test-secret-key"
        mock_settings.LANGFUSE_PUBLIC_KEY = "test-public-key"
        mock_settings.LANGFUSE_HOST = "https://test.langfuse.com"
        mock_settings.LANGFUSE_SAMPLE_RATE = 1.0
        mock_settings.APP_ENV.value = "test"

        # Mock Langfuse CallbackHandler
        with patch("app.agents.service.CallbackHandler") as mock_handler_class:
            mock_handler_instance = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "test-trace-id"
            mock_handler_instance.trace = mock_trace
            mock_handler_instance.langfuse.trace.return_value = mock_trace
            mock_handler_class.return_value = mock_handler_instance

            # Call the method
            handler = agent_service._create_langfuse_handler(
                user_id="test-user-id",
                trace_name="test_trace",
                metadata={"test_key": "test_value"},
            )

            # Verify handler was created with correct parameters
            assert handler is not None
            mock_handler_class.assert_called_once_with(
                secret_key="test-secret-key",
                public_key="test-public-key",
                host="https://test.langfuse.com",
                sample_rate=1.0,
            )

            # Verify trace was created with metadata
            mock_handler_instance.langfuse.trace.assert_called_once_with(
                name="test_trace",
                user_id="test-user-id",
                metadata={
                    "test_key": "test_value",
                    "user_id": "test-user-id",
                    "app_env": "test",
                },
            )

    @patch("app.agents.service.settings")
    def test_handler_not_created_when_disabled(
        self,
        mock_settings: Mock,
        agent_service: AgentService,
    ) -> None:
        """Test handler is None when Langfuse is disabled."""
        mock_settings.LANGFUSE_ENABLED = False
        mock_settings.LANGFUSE_SECRET_KEY = "test-secret-key"
        mock_settings.LANGFUSE_PUBLIC_KEY = "test-public-key"

        handler = agent_service._create_langfuse_handler(
            user_id="test-user-id",
        )

        assert handler is None

    @patch("app.agents.service.settings")
    def test_handler_not_created_when_missing_secret_key(
        self,
        mock_settings: Mock,
        agent_service: AgentService,
    ) -> None:
        """Test handler is None when secret key is missing."""
        mock_settings.LANGFUSE_ENABLED = True
        mock_settings.LANGFUSE_SECRET_KEY = None
        mock_settings.LANGFUSE_PUBLIC_KEY = "test-public-key"

        handler = agent_service._create_langfuse_handler(
            user_id="test-user-id",
        )

        assert handler is None

    @patch("app.agents.service.settings")
    def test_handler_not_created_when_missing_public_key(
        self,
        mock_settings: Mock,
        agent_service: AgentService,
    ) -> None:
        """Test handler is None when public key is missing."""
        mock_settings.LANGFUSE_ENABLED = True
        mock_settings.LANGFUSE_SECRET_KEY = "test-secret-key"
        mock_settings.LANGFUSE_PUBLIC_KEY = None

        handler = agent_service._create_langfuse_handler(
            user_id="test-user-id",
        )

        assert handler is None

    @patch("app.agents.service.CallbackHandler", None)
    def test_handler_not_created_when_package_not_installed(
        self,
        agent_service: AgentService,
    ) -> None:
        """Test handler is None when Langfuse package is not installed."""
        handler = agent_service._create_langfuse_handler(
            user_id="test-user-id",
        )

        assert handler is None

    @patch("app.agents.service.settings")
    def test_handler_creation_exception_handled_gracefully(
        self,
        mock_settings: Mock,
        agent_service: AgentService,
    ) -> None:
        """Test handler creation exception is caught and None is returned."""
        mock_settings.LANGFUSE_ENABLED = True
        mock_settings.LANGFUSE_SECRET_KEY = "test-secret-key"
        mock_settings.LANGFUSE_PUBLIC_KEY = "test-public-key"

        with patch("app.agents.service.CallbackHandler") as mock_handler_class:
            mock_handler_class.side_effect = Exception("Connection error")

            handler = agent_service._create_langfuse_handler(
                user_id="test-user-id",
            )

            assert handler is None


class TestRunAgent:
    """Test agent execution with various scenarios."""

    @pytest.mark.asyncio
    async def test_successful_agent_execution_without_tracing(
        self,
        agent_service: AgentService,
        mock_user: User,
    ) -> None:
        """Test successful agent execution without Langfuse tracing."""
        # Mock the agent invocation
        mock_message = MagicMock()
        mock_message.content = "Test response from agent"

        with patch("app.agents.service.ainvoke_agent", new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = {
                "messages": [mock_message],
                "plan": "Test plan",
                "user_id": str(mock_user.id),
            }

            # Mock Langfuse handler creation to return None
            with patch.object(agent_service, "_create_langfuse_handler", return_value=None):
                result = await agent_service.run_agent(
                    user=mock_user,
                    message="Test message",
                )

                # Verify result structure
                assert result["response"] == "Test response from agent"
                assert result["status"] == "success"
                assert result["trace_id"] is None
                assert result["plan"] == "Test plan"
                assert "thread_id" in result
                assert "run_id" in result
                assert "latency_ms" in result
                assert result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_successful_agent_execution_with_tracing(
        self,
        agent_service: AgentService,
        mock_user: User,
    ) -> None:
        """Test successful agent execution with Langfuse tracing."""
        # Mock the agent invocation
        mock_message = MagicMock()
        mock_message.content = "Test response from agent"

        # Mock Langfuse handler
        mock_handler = MagicMock()
        mock_trace = MagicMock()
        mock_trace.id = "test-trace-id-123"
        mock_handler.trace = mock_trace
        mock_handler.langfuse.flush = MagicMock()

        with patch("app.agents.service.ainvoke_agent", new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = {
                "messages": [mock_message],
                "plan": "Test plan",
                "user_id": str(mock_user.id),
            }

            with patch.object(agent_service, "_create_langfuse_handler", return_value=mock_handler):
                with patch("app.agents.service.app_logging.set_trace_id") as mock_set_trace:
                    result = await agent_service.run_agent(
                        user=mock_user,
                        message="Test message",
                    )

                    # Verify tracing was set up
                    mock_set_trace.assert_called_once_with("test-trace-id-123")

                    # Verify result includes trace_id
                    assert result["trace_id"] == "test-trace-id-123"
                    assert result["status"] == "success"

                    # Verify flush was called
                    mock_handler.langfuse.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_execution_with_custom_thread_id(
        self,
        agent_service: AgentService,
        mock_user: User,
    ) -> None:
        """Test agent execution with user-provided thread_id."""
        custom_thread_id = "custom-thread-123"
        mock_message = MagicMock()
        mock_message.content = "Test response"

        with patch("app.agents.service.ainvoke_agent", new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = {
                "messages": [mock_message],
                "plan": None,
                "user_id": str(mock_user.id),
            }

            with patch.object(agent_service, "_create_langfuse_handler", return_value=None):
                result = await agent_service.run_agent(
                    user=mock_user,
                    message="Test message",
                    thread_id=custom_thread_id,
                )

                # Verify thread_id is preserved
                assert result["thread_id"] == custom_thread_id

                # Verify ainvoke was called with the thread_id
                mock_ainvoke.assert_called_once()
                call_kwargs = mock_ainvoke.call_args.kwargs
                assert call_kwargs["thread_id"] == custom_thread_id

    @pytest.mark.asyncio
    async def test_agent_execution_with_metadata(
        self,
        agent_service: AgentService,
        mock_user: User,
    ) -> None:
        """Test agent execution with custom metadata."""
        custom_metadata = {"source": "api", "version": "v1"}
        mock_message = MagicMock()
        mock_message.content = "Test response"

        mock_handler = MagicMock()
        mock_trace = MagicMock()
        mock_trace.id = "trace-123"
        mock_handler.trace = mock_trace
        mock_handler.langfuse.flush = MagicMock()

        with patch("app.agents.service.ainvoke_agent", new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = {
                "messages": [mock_message],
                "plan": None,
                "user_id": str(mock_user.id),
            }

            with patch.object(agent_service, "_create_langfuse_handler", return_value=mock_handler) as mock_create:
                with patch("app.agents.service.app_logging.set_trace_id"):
                    await agent_service.run_agent(
                        user=mock_user,
                        message="Test message",
                        metadata=custom_metadata,
                    )

                    # Verify metadata was passed to handler
                    call_kwargs = mock_create.call_args.kwargs
                    assert "source" in call_kwargs["metadata"]
                    assert call_kwargs["metadata"]["source"] == "api"

    @pytest.mark.asyncio
    async def test_agent_execution_handles_list_content(
        self,
        agent_service: AgentService,
        mock_user: User,
    ) -> None:
        """Test agent execution handles non-string message content."""
        # Mock the agent invocation with list content
        mock_message = MagicMock()
        mock_message.content = ["part1", "part2"]

        with patch("app.agents.service.ainvoke_agent", new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = {
                "messages": [mock_message],
                "plan": None,
                "user_id": str(mock_user.id),
            }

            with patch.object(agent_service, "_create_langfuse_handler", return_value=None):
                result = await agent_service.run_agent(
                    user=mock_user,
                    message="Test message",
                )

                # Verify content was converted to string
                assert result["response"] == str(["part1", "part2"])
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_agent_execution_handles_empty_messages(
        self,
        agent_service: AgentService,
        mock_user: User,
    ) -> None:
        """Test agent execution handles empty messages list."""
        with patch("app.agents.service.ainvoke_agent", new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = {
                "messages": [],
                "plan": None,
                "user_id": str(mock_user.id),
            }

            with patch.object(agent_service, "_create_langfuse_handler", return_value=None):
                result = await agent_service.run_agent(
                    user=mock_user,
                    message="Test message",
                )

                # Verify empty response
                assert result["response"] == ""
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_agent_execution_handles_exception(
        self,
        agent_service: AgentService,
        mock_user: User,
    ) -> None:
        """Test agent execution handles and re-raises exceptions."""
        with patch("app.agents.service.ainvoke_agent", new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.side_effect = ValueError("Test error")

            with patch.object(agent_service, "_create_langfuse_handler", return_value=None):
                with pytest.raises(ValueError, match="Test error"):
                    await agent_service.run_agent(
                        user=mock_user,
                        message="Test message",
                    )

    @pytest.mark.asyncio
    async def test_agent_execution_exception_with_tracing(
        self,
        agent_service: AgentService,
        mock_user: User,
    ) -> None:
        """Test agent execution captures trace_id even on exception."""
        mock_handler = MagicMock()
        mock_trace = MagicMock()
        mock_trace.id = "error-trace-id"
        mock_handler.trace = mock_trace
        mock_handler.langfuse.flush = MagicMock()

        with patch("app.agents.service.ainvoke_agent", new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.side_effect = RuntimeError("Agent failed")

            with patch.object(agent_service, "_create_langfuse_handler", return_value=mock_handler):
                with patch("app.agents.service.app_logging.set_trace_id"):
                    with pytest.raises(RuntimeError, match="Agent failed"):
                        await agent_service.run_agent(
                            user=mock_user,
                            message="Test message",
                        )

                    # Verify flush was still called in finally block
                    mock_handler.langfuse.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_execution_handles_flush_exception(
        self,
        agent_service: AgentService,
        mock_user: User,
    ) -> None:
        """Test agent execution handles Langfuse flush exceptions gracefully."""
        mock_message = MagicMock()
        mock_message.content = "Test response"

        mock_handler = MagicMock()
        mock_trace = MagicMock()
        mock_trace.id = "trace-123"
        mock_handler.trace = mock_trace
        mock_handler.langfuse.flush.side_effect = Exception("Flush failed")

        with patch("app.agents.service.ainvoke_agent", new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = {
                "messages": [mock_message],
                "plan": None,
                "user_id": str(mock_user.id),
            }

            with patch.object(agent_service, "_create_langfuse_handler", return_value=mock_handler):
                with patch("app.agents.service.app_logging.set_trace_id"):
                    # Should not raise despite flush error
                    result = await agent_service.run_agent(
                        user=mock_user,
                        message="Test message",
                    )

                    assert result["status"] == "success"


class TestGetRunHistory:
    """Test run history retrieval."""

    @pytest.mark.asyncio
    async def test_get_run_history_returns_placeholder(
        self,
        agent_service: AgentService,
        mock_user: User,
    ) -> None:
        """Test get_run_history returns placeholder response."""
        result = await agent_service.get_run_history(
            user=mock_user,
            limit=20,
            offset=10,
        )

        assert result["runs"] == []
        assert result["total"] == 0
        assert result["limit"] == 20
        assert result["offset"] == 10
        assert "message" in result

    @pytest.mark.asyncio
    async def test_get_run_history_default_pagination(
        self,
        agent_service: AgentService,
        mock_user: User,
    ) -> None:
        """Test get_run_history uses default pagination values."""
        result = await agent_service.get_run_history(
            user=mock_user,
        )

        assert result["limit"] == 10
        assert result["offset"] == 0


class TestGetRunById:
    """Test run retrieval by ID."""

    @pytest.mark.asyncio
    async def test_get_run_by_id_returns_none(
        self,
        agent_service: AgentService,
        mock_user: User,
    ) -> None:
        """Test get_run_by_id returns None (placeholder)."""
        result = await agent_service.get_run_by_id(
            user=mock_user,
            run_id="test-run-id",
        )

        assert result is None


class TestCreateAgentService:
    """Test agent service factory function."""

    def test_create_agent_service_returns_instance(
        self,
        mock_session: Mock,
    ) -> None:
        """Test factory function creates AgentService instance."""
        service = create_agent_service(session=mock_session)

        assert isinstance(service, AgentService)
        assert service.session == mock_session

    def test_create_agent_service_with_real_session(
        self,
        db: Session,
    ) -> None:
        """Test factory function works with real database session."""
        service = create_agent_service(session=db)

        assert isinstance(service, AgentService)
        assert service.session == db
