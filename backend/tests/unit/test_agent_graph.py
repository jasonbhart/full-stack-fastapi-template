"""Unit tests for agent graph and checkpointer functionality."""

import pytest
from sqlmodel import Session

from app.agents.graph import (
    create_agent_graph,
    invoke_agent,
)
from app.models import User


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user for agent tests."""
    from app import crud
    from app.core.config import settings

    user = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert user is not None
    return user


def test_create_agent_graph_without_checkpointer(db: Session) -> None:
    """Test creating agent graph without checkpointer."""
    graph = create_agent_graph(session=db, checkpointer=None)

    assert graph is not None
    # Graph should be compiled and ready to use
    assert hasattr(graph, "invoke")
    assert hasattr(graph, "ainvoke")


def test_checkpointer_context_manager_lifecycle() -> None:
    """Test that checkpointer context manager is properly managed.

    This regression test ensures the checkpointer is created and cleaned up
    correctly using the context manager pattern. It verifies the fix for
    the issue where checkpointers were being closed before use.
    """
    from unittest.mock import patch, MagicMock
    from app.agents.graph import _get_connection_string
    from langgraph.checkpoint.postgres import PostgresSaver

    # Get the connection string (this validates the helper function)
    conn_str = _get_connection_string()
    assert "postgresql://" in conn_str
    assert "+psycopg" not in conn_str  # Should be stripped

    # Mock the PostgresSaver context manager to verify it's used correctly
    mock_checkpointer = MagicMock(spec=PostgresSaver)
    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = mock_checkpointer
    mock_context_manager.__exit__.return_value = None

    with patch.object(PostgresSaver, "from_conn_string", return_value=mock_context_manager):
        with patch("app.agents.graph.create_agent_graph") as mock_create_graph:
            mock_graph = MagicMock()
            mock_graph.invoke.return_value = {
                "messages": [MagicMock(content="test response")],
                "plan": None,
                "user_id": "test-user",
            }
            mock_create_graph.return_value = mock_graph

            # Call invoke_agent - this should use the context manager properly
            from app.agents.graph import invoke_agent

            result = invoke_agent(
                message="test message",
                user_id="test-user",
                session=None,
            )

            # Verify context manager was entered and exited
            mock_context_manager.__enter__.assert_called_once()
            mock_context_manager.__exit__.assert_called_once()

            # Verify checkpointer.setup() was called
            mock_checkpointer.setup.assert_called_once()

            # Verify result was returned
            assert result is not None
            assert "messages" in result
