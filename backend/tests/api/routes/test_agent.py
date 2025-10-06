"""API tests for agent endpoints.

This module tests the agent API endpoints covering:
- Authentication and authorization
- Rate limiting behavior
- Error handling and validation
- Pagination and filtering
- Response schema validation
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def create_random_agent_run(db: Session, user: User | None = None) -> Any:
    """Create a random agent run for testing.

    Args:
        db: Database session
        user: Optional user to assign the run to (creates random user if not provided)

    Returns:
        Created AgentRun instance
    """
    if user is None:
        user = create_random_user(db)

    return crud.create_agent_run(
        session=db,
        user_id=user.id,
        input=f"Test question: {random_lower_string()}",
        output=f"Test answer: {random_lower_string()}",
        status="success",
        latency_ms=1500,
        prompt_tokens=100,
        completion_tokens=200,
        trace_id=f"trace-{random_lower_string()}",
    )


class TestAgentRun:
    """Tests for POST /api/v1/agent/run endpoint."""

    def test_run_agent_unauthenticated(self, client: TestClient) -> None:
        """Test running agent without authentication returns 401."""
        data = {"message": "Hello, agent!"}
        response = client.post(
            f"{settings.API_V1_STR}/agent/run",
            json=data,
        )
        assert response.status_code == 401

    @patch("app.api.routes.agent.create_agent_service")
    def test_run_agent_success(
        self,
        mock_create_service: MagicMock,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
    ) -> None:
        """Test successful agent execution."""
        # Mock the agent service
        mock_service = MagicMock()
        mock_service.run_agent = AsyncMock(return_value={
            "response": "Hello! How can I help you?",
            "thread_id": "thread-123",
            "trace_id": "trace-456",
            "status": "success",
            "latency_ms": 1500,
            "plan": "Answer the user's greeting",
        })
        mock_create_service.return_value = mock_service

        data = {"message": "Hello, agent!"}
        response = client.post(
            f"{settings.API_V1_STR}/agent/run",
            headers=normal_user_token_headers,
            json=data,
        )

        assert response.status_code == 200
        content = response.json()

        # Validate response schema
        assert "response" in content
        assert content["response"] == "Hello! How can I help you?"
        assert "thread_id" in content
        assert content["thread_id"] == "thread-123"
        assert "trace_id" in content
        assert "trace_url" in content
        assert "run_id" in content
        assert "latency_ms" in content
        assert content["latency_ms"] == 1500
        assert "status" in content
        assert content["status"] == "success"
        assert "plan" in content
        assert content["plan"] == "Answer the user's greeting"

    @patch("app.api.routes.agent.create_agent_service")
    def test_run_agent_with_thread_id(
        self,
        mock_create_service: MagicMock,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
    ) -> None:
        """Test agent execution with thread_id for conversation continuity."""
        mock_service = MagicMock()
        mock_service.run_agent = AsyncMock(return_value={
            "response": "Continuing our conversation...",
            "thread_id": "existing-thread-123",
            "status": "success",
            "latency_ms": 1200,
        })
        mock_create_service.return_value = mock_service

        data = {
            "message": "What did we talk about?",
            "thread_id": "existing-thread-123",
        }
        response = client.post(
            f"{settings.API_V1_STR}/agent/run",
            headers=normal_user_token_headers,
            json=data,
        )

        assert response.status_code == 200
        content = response.json()
        assert content["thread_id"] == "existing-thread-123"

    @patch("app.api.routes.agent.create_agent_service")
    def test_run_agent_with_metadata(
        self,
        mock_create_service: MagicMock,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
    ) -> None:
        """Test agent execution with custom run metadata."""
        mock_service = MagicMock()
        mock_service.run_agent = AsyncMock(return_value={
            "response": "Response with metadata",
            "thread_id": "thread-789",
            "status": "success",
            "latency_ms": 1000,
        })
        mock_create_service.return_value = mock_service

        data = {
            "message": "Test with metadata",
            "run_metadata": {"source": "api_test", "version": "v1"},
        }
        response = client.post(
            f"{settings.API_V1_STR}/agent/run",
            headers=normal_user_token_headers,
            json=data,
        )

        assert response.status_code == 200

    def test_run_agent_empty_message(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
    ) -> None:
        """Test agent execution with empty message returns 422."""
        data = {"message": ""}
        response = client.post(
            f"{settings.API_V1_STR}/agent/run",
            headers=normal_user_token_headers,
            json=data,
        )
        assert response.status_code == 422

    def test_run_agent_message_too_long(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
    ) -> None:
        """Test agent execution with message exceeding max length returns 422."""
        data = {"message": "x" * 10001}  # Exceeds 10000 char limit
        response = client.post(
            f"{settings.API_V1_STR}/agent/run",
            headers=normal_user_token_headers,
            json=data,
        )
        assert response.status_code == 422

    @patch("app.api.routes.agent.create_agent_service")
    def test_run_agent_service_error(
        self,
        mock_create_service: MagicMock,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
    ) -> None:
        """Test agent execution handles service errors gracefully."""
        mock_service = MagicMock()
        mock_service.run_agent = AsyncMock(side_effect=ValueError("Agent error"))
        mock_create_service.return_value = mock_service

        data = {"message": "This will fail"}
        response = client.post(
            f"{settings.API_V1_STR}/agent/run",
            headers=normal_user_token_headers,
            json=data,
        )

        assert response.status_code == 500
        content = response.json()
        assert "detail" in content
        assert "Agent execution failed" in content["detail"]


class TestGetAgentRuns:
    """Tests for GET /api/v1/agent/runs endpoint."""

    def test_get_runs_unauthenticated(self, client: TestClient) -> None:
        """Test getting runs without authentication returns 401."""
        response = client.get(f"{settings.API_V1_STR}/agent/runs")
        assert response.status_code == 401

    def test_get_runs_success(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Test successful retrieval of agent runs."""
        # Get the current user
        user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
        assert user is not None

        # Create test runs for this user
        run1 = create_random_agent_run(db, user)
        run2 = create_random_agent_run(db, user)

        response = client.get(
            f"{settings.API_V1_STR}/agent/runs",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 200
        content = response.json()

        # Validate response schema
        assert "data" in content
        assert isinstance(content["data"], list)
        assert "total" in content
        assert "limit" in content
        assert "offset" in content

        # Verify at least our runs are present
        assert content["total"] >= 2

        # Validate run schema
        if content["data"]:
            run = content["data"][0]
            assert "id" in run
            assert "user_id" in run
            assert "thread_id" in run
            assert "input" in run
            assert "output" in run
            assert "status" in run
            assert "latency_ms" in run
            assert "trace_id" in run
            assert "trace_url" in run
            assert "created_at" in run
            assert "prompt_tokens" in run
            assert "completion_tokens" in run

    def test_get_runs_pagination(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Test pagination parameters work correctly."""
        user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
        assert user is not None

        # Create multiple runs
        for _ in range(5):
            create_random_agent_run(db, user)

        # Test with limit and offset
        response = client.get(
            f"{settings.API_V1_STR}/agent/runs?skip=2&limit=2",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 200
        content = response.json()
        assert content["limit"] == 2
        assert content["offset"] == 2
        assert len(content["data"]) <= 2

    def test_get_runs_limit_enforcement(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
    ) -> None:
        """Test that limit is capped at 1000."""
        response = client.get(
            f"{settings.API_V1_STR}/agent/runs?limit=2000",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 200
        content = response.json()
        assert content["limit"] == 1000  # Should be capped

    def test_get_runs_filter_by_status(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Test filtering runs by status."""
        user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
        assert user is not None

        # Create runs with different statuses
        crud.create_agent_run(
            session=db,
            user_id=user.id,
            input="Success test",
            output="Success output",
            status="success",
        )
        crud.create_agent_run(
            session=db,
            user_id=user.id,
            input="Error test",
            output="Error output",
            status="error",
        )

        # Filter by success status
        response = client.get(
            f"{settings.API_V1_STR}/agent/runs?status=success",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 200
        content = response.json()
        # All returned runs should have success status
        for run in content["data"]:
            assert run["status"] == "success"

    def test_get_runs_search(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Test search functionality in run history."""
        user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
        assert user is not None

        # Create run with specific content
        unique_word = f"UNIQUEWORD{random_lower_string()}"
        crud.create_agent_run(
            session=db,
            user_id=user.id,
            input=f"Question about {unique_word}",
            output="Answer",
            status="success",
        )

        # Search for the unique word
        response = client.get(
            f"{settings.API_V1_STR}/agent/runs?search={unique_word}",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 200
        content = response.json()
        assert content["total"] >= 1
        # At least one result should contain the search term
        found = any(unique_word in run["input"] for run in content["data"])
        assert found

    def test_get_runs_only_own_runs(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Test users only see their own runs."""
        current_user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
        assert current_user is not None

        # Create run for another user
        other_user = create_random_user(db)
        other_run = create_random_agent_run(db, other_user)

        response = client.get(
            f"{settings.API_V1_STR}/agent/runs",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 200
        content = response.json()

        # Verify other user's run is not in results
        run_ids = [run["id"] for run in content["data"]]
        assert str(other_run.id) not in run_ids

    def test_get_runs_empty_result(
        self,
        client: TestClient,
        db: Session,
    ) -> None:
        """Test getting runs for user with no runs returns empty list."""
        # Create a new user with no runs
        new_user = create_random_user(db)
        from tests.utils.user import authentication_token_from_email
        headers = authentication_token_from_email(
            client=client,
            email=new_user.email,
            db=db,
        )

        response = client.get(
            f"{settings.API_V1_STR}/agent/runs",
            headers=headers,
        )

        assert response.status_code == 200
        content = response.json()
        assert content["data"] == []
        assert content["total"] == 0


class TestGetAgentRunById:
    """Tests for GET /api/v1/agent/runs/{run_id} endpoint."""

    def test_get_run_unauthenticated(self, client: TestClient) -> None:
        """Test getting run without authentication returns 401."""
        run_id = uuid.uuid4()
        response = client.get(f"{settings.API_V1_STR}/agent/runs/{run_id}")
        assert response.status_code == 401

    def test_get_run_success(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Test successful retrieval of specific run."""
        user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
        assert user is not None

        run = create_random_agent_run(db, user)

        response = client.get(
            f"{settings.API_V1_STR}/agent/runs/{run.id}",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 200
        content = response.json()
        assert content["id"] == str(run.id)
        assert content["input"] == run.input
        assert content["output"] == run.output

    def test_get_run_not_found(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
    ) -> None:
        """Test getting non-existent run returns 404."""
        non_existent_id = uuid.uuid4()
        response = client.get(
            f"{settings.API_V1_STR}/agent/runs/{non_existent_id}",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 404
        content = response.json()
        assert content["detail"] == "Agent run not found"

    def test_get_run_forbidden(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Test users cannot access other users' runs."""
        # Create run for another user
        other_user = create_random_user(db)
        other_run = create_random_agent_run(db, other_user)

        response = client.get(
            f"{settings.API_V1_STR}/agent/runs/{other_run.id}",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 403
        content = response.json()
        assert "Not enough permissions" in content["detail"]

    def test_get_run_superuser_access(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Test superuser can access any run."""
        # Create run for another user
        other_user = create_random_user(db)
        other_run = create_random_agent_run(db, other_user)

        response = client.get(
            f"{settings.API_V1_STR}/agent/runs/{other_run.id}",
            headers=superuser_token_headers,
        )

        assert response.status_code == 200
        content = response.json()
        assert content["id"] == str(other_run.id)


class TestTriggerEvaluation:
    """Tests for POST /api/v1/agent/evaluations endpoint."""

    def test_trigger_evaluation_unauthenticated(self, client: TestClient) -> None:
        """Test triggering evaluation without authentication returns 401."""
        data = {
            "run_id": str(uuid.uuid4()),
            "metric_name": "accuracy",
            "score": 0.95,
        }
        response = client.post(
            f"{settings.API_V1_STR}/agent/evaluations",
            json=data,
        )
        assert response.status_code == 401

    def test_trigger_evaluation_success(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Test successful evaluation creation."""
        user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
        assert user is not None

        run = create_random_agent_run(db, user)

        data = {
            "run_id": str(run.id),
            "metric_name": "helpfulness",
            "score": 0.85,
            "eval_metadata": {"evaluator": "human", "comments": "Very helpful"},
        }
        response = client.post(
            f"{settings.API_V1_STR}/agent/evaluations",
            headers=normal_user_token_headers,
            json=data,
        )

        assert response.status_code == 200
        content = response.json()
        assert "message" in content
        assert "helpfulness" in content["message"]
        assert str(run.id) in content["message"]

    def test_trigger_evaluation_run_not_found(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
    ) -> None:
        """Test evaluation on non-existent run returns 404."""
        data = {
            "run_id": str(uuid.uuid4()),
            "metric_name": "accuracy",
            "score": 0.95,
        }
        response = client.post(
            f"{settings.API_V1_STR}/agent/evaluations",
            headers=normal_user_token_headers,
            json=data,
        )

        assert response.status_code == 404
        content = response.json()
        assert content["detail"] == "Agent run not found"

    def test_trigger_evaluation_forbidden(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Test users cannot evaluate other users' runs."""
        # Create run for another user
        other_user = create_random_user(db)
        other_run = create_random_agent_run(db, other_user)

        data = {
            "run_id": str(other_run.id),
            "metric_name": "accuracy",
            "score": 0.95,
        }
        response = client.post(
            f"{settings.API_V1_STR}/agent/evaluations",
            headers=normal_user_token_headers,
            json=data,
        )

        assert response.status_code == 403
        content = response.json()
        assert "Not enough permissions" in content["detail"]

    def test_trigger_evaluation_superuser_access(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Test superuser can evaluate any run."""
        # Create run for another user
        other_user = create_random_user(db)
        other_run = create_random_agent_run(db, other_user)

        data = {
            "run_id": str(other_run.id),
            "metric_name": "accuracy",
            "score": 0.95,
        }
        response = client.post(
            f"{settings.API_V1_STR}/agent/evaluations",
            headers=superuser_token_headers,
            json=data,
        )

        assert response.status_code == 200

    def test_trigger_evaluation_validation(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Test evaluation validation for required fields."""
        user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
        assert user is not None

        run = create_random_agent_run(db, user)

        # Missing metric_name
        data = {
            "run_id": str(run.id),
            "score": 0.95,
        }
        response = client.post(
            f"{settings.API_V1_STR}/agent/evaluations",
            headers=normal_user_token_headers,
            json=data,
        )
        assert response.status_code == 422

        # Missing score
        data = {
            "run_id": str(run.id),
            "metric_name": "accuracy",
        }
        response = client.post(
            f"{settings.API_V1_STR}/agent/evaluations",
            headers=normal_user_token_headers,
            json=data,
        )
        assert response.status_code == 422


class TestAgentHealth:
    """Tests for GET /api/v1/agent/health endpoint."""

    def test_health_check_no_auth_required(self, client: TestClient) -> None:
        """Test health check endpoint doesn't require authentication."""
        response = client.get(f"{settings.API_V1_STR}/agent/health")
        assert response.status_code == 200

    def test_health_check_response_schema(self, client: TestClient) -> None:
        """Test health check returns correct schema."""
        response = client.get(f"{settings.API_V1_STR}/agent/health")

        assert response.status_code == 200
        content = response.json()

        # Validate required fields
        assert "status" in content
        assert content["status"] in ["healthy", "degraded", "unhealthy"]
        assert "langfuse_enabled" in content
        assert isinstance(content["langfuse_enabled"], bool)
        assert "langfuse_configured" in content
        assert isinstance(content["langfuse_configured"], bool)
        assert "model_name" in content
        assert isinstance(content["model_name"], str)
        assert "available_tools" in content
        assert isinstance(content["available_tools"], int)
        assert content["available_tools"] >= 0

    @patch("app.api.routes.agent.settings")
    def test_health_check_degraded_when_langfuse_misconfigured(
        self,
        mock_settings: MagicMock,
        client: TestClient,
    ) -> None:
        """Test health returns degraded when Langfuse is enabled but not configured."""
        mock_settings.LANGFUSE_ENABLED = True
        mock_settings.LANGFUSE_SECRET_KEY = None
        mock_settings.LANGFUSE_PUBLIC_KEY = None
        mock_settings.LLM_MODEL_NAME = "gpt-4"

        response = client.get(f"{settings.API_V1_STR}/agent/health")

        assert response.status_code == 200
        content = response.json()
        assert content["status"] == "degraded"
        assert content["langfuse_enabled"] is True
        assert content["langfuse_configured"] is False


class TestRateLimiting:
    """Tests for rate limiting on agent endpoints."""

    @pytest.mark.skipif(
        not settings.RATE_LIMIT_ENABLED,
        reason="Rate limiting is disabled in test environment"
    )
    @patch("app.api.routes.agent.create_agent_service")
    def test_rate_limit_enforcement(
        self,
        mock_create_service: MagicMock,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
    ) -> None:
        """Test rate limiting is enforced on agent run endpoint.

        Note: This test may be affected by other tests that have already
        made requests. We primarily verify that rate limiting returns 429
        when exceeded.
        """
        mock_service = MagicMock()
        mock_service.run_agent = AsyncMock(return_value={
            "response": "Test response",
            "thread_id": "thread-123",
            "status": "success",
            "latency_ms": 100,
        })
        mock_create_service.return_value = mock_service

        # Make requests until we hit the rate limit
        # We expect to hit 429 within a reasonable number of requests
        limit = settings.RATE_LIMIT_PER_MINUTE
        hit_rate_limit = False

        for i in range(limit + 10):
            response = client.post(
                f"{settings.API_V1_STR}/agent/run",
                headers=normal_user_token_headers,
                json={"message": f"Request {i}"},
            )

            if response.status_code == 429:
                # Successfully hit rate limit
                hit_rate_limit = True
                break
            elif response.status_code == 200:
                # Request succeeded, keep going
                continue
            else:
                # Unexpected status code
                pytest.fail(f"Unexpected status code: {response.status_code}")

        # We should have hit the rate limit
        assert hit_rate_limit, "Rate limit was not enforced"

    @pytest.mark.skipif(
        not settings.RATE_LIMIT_ENABLED,
        reason="Rate limiting is disabled in test environment"
    )
    def test_rate_limit_headers(
        self,
        client: TestClient,
        normal_user_token_headers: dict[str, str],
    ) -> None:
        """Test rate limit headers are included in successful responses.

        FastAPI-Limiter automatically adds standard rate limit headers:
        - X-RateLimit-Limit: Maximum requests allowed in the window
        - X-RateLimit-Remaining: Requests remaining in current window
        - X-RateLimit-Reset: Time when the limit resets
        """
        response = client.get(
            f"{settings.API_V1_STR}/agent/runs",
            headers=normal_user_token_headers,
        )

        # Verify request succeeds (not rate limited)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Verify all standard rate limit headers are present
        assert "X-RateLimit-Limit" in response.headers, "Missing X-RateLimit-Limit header"
        assert "X-RateLimit-Remaining" in response.headers, "Missing X-RateLimit-Remaining header"
        assert "X-RateLimit-Reset" in response.headers, "Missing X-RateLimit-Reset header"
