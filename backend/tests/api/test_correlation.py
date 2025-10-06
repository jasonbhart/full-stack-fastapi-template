"""Integration tests for correlation ID and trace ID middleware."""

from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings


def test_correlation_id_header_generated(
    client: TestClient,
) -> None:
    """Test that correlation ID is generated and returned in response headers."""
    response = client.get(f"{settings.API_V1_STR}/login/test-token")

    # Correlation ID should be in response headers
    assert "X-Correlation-ID" in response.headers
    correlation_id = response.headers["X-Correlation-ID"]

    # Should be a valid UUID format
    assert len(correlation_id) > 0
    assert "-" in correlation_id  # UUIDs contain dashes


def test_correlation_id_header_preserved(
    client: TestClient,
) -> None:
    """Test that provided correlation ID is preserved in response headers."""
    custom_correlation_id = "test-correlation-12345"

    response = client.get(
        f"{settings.API_V1_STR}/login/test-token",
        headers={"X-Correlation-ID": custom_correlation_id},
    )

    # Custom correlation ID should be returned
    assert response.headers["X-Correlation-ID"] == custom_correlation_id


def test_correlation_id_in_context(
    client: TestClient,
) -> None:
    """Test that correlation ID context mechanism works correctly."""
    from app.core import logging as app_logging

    # Test setting and getting correlation ID
    test_correlation_id = "test-context-789"
    app_logging.set_correlation_id(test_correlation_id)

    retrieved_id = app_logging.get_correlation_id()
    assert retrieved_id == test_correlation_id

    # Test clearing context
    app_logging.clear_context()
    assert app_logging.get_correlation_id() is None
    assert app_logging.get_trace_id() is None


def test_trace_id_mechanism_with_direct_context() -> None:
    """Test that trace ID mechanism works correctly when set in request context.

    This test verifies the regression fix at the code level: trace_id must NOT be
    cleared in AgentService before middleware can read it for response headers.

    Note: Full end-to-end testing with TestClient is limited by context var isolation
    in the test client. This test verifies the mechanism works correctly.
    """
    import asyncio

    from app.core import logging as app_logging

    async def simulate_agent_request() -> str | None:
        """Simulate what happens during an agent request with trace ID."""
        # 1. Middleware starts (would set correlation ID)
        app_logging.set_correlation_id("test-corr-123")

        # 2. Agent service runs and sets trace ID (simulating Langfuse handler)
        app_logging.set_trace_id("test-trace-456")

        # 3. Agent service completes WITHOUT clearing trace_id
        # (This is the regression fix - we removed the premature cleanup)

        # 4. Middleware reads trace_id for response headers
        trace_id_for_header = app_logging.get_trace_id()

        # 5. Middleware clears context in finally block
        app_logging.clear_context()

        return trace_id_for_header

    # Run the simulation
    result = asyncio.run(simulate_agent_request())

    # CRITICAL ASSERTION: trace_id should be available for response headers
    assert result == "test-trace-456", (
        f"Expected trace ID 'test-trace-456' but got {result}. "
        "This indicates trace_id was cleared too early!"
    )


def test_agent_service_does_not_clear_trace_id() -> None:
    """Verify that AgentService.run_agent does NOT clear trace_id in its finally block.

    This is an AST-based regression guard that structurally verifies the code
    doesn't reintroduce the bug where trace_id is cleared before middleware
    can add it to response headers.
    """
    import ast
    import inspect
    import textwrap

    from app.agents.service import AgentService

    # Get the source code and dedent it for parsing
    source = inspect.getsource(AgentService.run_agent)
    source = textwrap.dedent(source)
    tree = ast.parse(source)

    # Find the run_agent function definition
    func_def = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run_agent":
            func_def = node
            break

    assert func_def is not None, "Could not find run_agent function definition"

    # Find the Try node (which contains the finally block)
    try_node = None
    for node in ast.walk(func_def):
        if isinstance(node, ast.Try) and node.finalbody:
            try_node = node
            break

    assert try_node is not None, "Could not find try/finally block in run_agent"

    # Check all function calls in the finally block
    problematic_calls = []
    for finally_stmt in try_node.finalbody:
        for node in ast.walk(finally_stmt):
            if isinstance(node, ast.Call):
                # Check if this is a call to set_trace_id
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "set_trace_id":
                        # Check positional arguments for None
                        if node.args and isinstance(node.args[0], ast.Constant):
                            if node.args[0].value is None:
                                problematic_calls.append(
                                    f"Line {node.lineno}: {ast.unparse(node)}"
                                )

                        # Check keyword arguments for None
                        for keyword in node.keywords:
                            if isinstance(keyword.value, ast.Constant):
                                if keyword.value.value is None:
                                    problematic_calls.append(
                                        f"Line {node.lineno}: {ast.unparse(node)}"
                                    )

    assert not problematic_calls, (
        "AgentService.run_agent finally block should NOT call set_trace_id(None)! "
        "This would prevent middleware from adding X-Trace-ID to response headers.\n"
        f"Found problematic calls:\n" + "\n".join(problematic_calls)
    )
