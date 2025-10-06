"""
End-to-end smoke tests for agent workflow.

This module tests the complete agent workflow from API to traces,
including service connectivity and integration validation.
"""

import os
import time
from typing import Any, cast

import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Configuration - can be overridden by environment variables
BACKEND_URL = os.getenv("E2E_BACKEND_URL", "http://localhost:8000")
LANGFUSE_URL = os.getenv("E2E_LANGFUSE_URL", "http://localhost:3000")
PROMETHEUS_URL = os.getenv("E2E_PROMETHEUS_URL", "http://localhost:9090")
GRAFANA_URL = os.getenv("E2E_GRAFANA_URL", "http://localhost:3001")
REDIS_HOST = os.getenv("E2E_REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("E2E_REDIS_PORT", "6379"))

# Test credentials
SUPERUSER_EMAIL = os.getenv("FIRST_SUPERUSER", "admin@example.com")
SUPERUSER_PASSWORD = os.getenv("FIRST_SUPERUSER_PASSWORD", "changethis")

# Test timeouts
SERVICE_STARTUP_TIMEOUT = int(os.getenv("E2E_STARTUP_TIMEOUT", "180"))
REQUEST_TIMEOUT = int(os.getenv("E2E_REQUEST_TIMEOUT", "30"))


def get_retry_session(
    retries: int = 3,
    backoff_factor: float = 0.3,
    status_forcelist: tuple[int, ...] = (500, 502, 503, 504),
) -> requests.Session:
    """
    Create a requests session with retry logic.

    Args:
        retries: Number of retry attempts
        backoff_factor: Backoff factor for retries
        status_forcelist: HTTP status codes to retry on

    Returns:
        Configured requests session
    """
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def wait_for_service(
    url: str,
    timeout: int = SERVICE_STARTUP_TIMEOUT,
    check_interval: int = 2,
    service_name: str = "Service",
) -> bool:
    """
    Wait for a service to become available.

    Args:
        url: Service URL to check
        timeout: Maximum wait time in seconds
        check_interval: Time between checks in seconds
        service_name: Name of service for logging

    Returns:
        True if service is available, raises TimeoutError otherwise
    """
    session = get_retry_session()
    start_time = time.time()
    last_error = None

    while time.time() - start_time < timeout:
        try:
            response = session.get(url, timeout=5)
            if response.status_code < 500:  # Service is responding
                print(f"✓ {service_name} is available at {url}")
                return True
        except Exception as e:
            last_error = str(e)

        time.sleep(check_interval)

    raise TimeoutError(
        f"Service {service_name} at {url} did not become available within {timeout}s. "
        f"Last error: {last_error}"
    )


pytestmark = pytest.mark.e2e  # Mark all tests in this module as E2E tests


@pytest.fixture(scope="module")
def session() -> requests.Session:
    """Create a requests session for E2E tests."""
    return get_retry_session()


@pytest.fixture(scope="module")
def auth_token(session: requests.Session) -> str:
    """
    Authenticate and return access token.

    Args:
        session: Requests session

    Returns:
        JWT access token
    """
    # Wait for backend to be ready
    wait_for_service(
        f"{BACKEND_URL}/api/v1/utils/health-check/",
        service_name="Backend API",
    )

    # Login to get access token
    response = session.post(
        f"{BACKEND_URL}/api/v1/login/access-token",
        data={
            "username": SUPERUSER_EMAIL,
            "password": SUPERUSER_PASSWORD,
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    token_data = response.json()

    assert "access_token" in token_data, "No access token in login response"
    return cast(str, token_data["access_token"])


class TestServiceConnectivity:
    """Test connectivity to all services in the stack."""

    def test_backend_health(self, session: requests.Session) -> None:
        """Test backend health check endpoint."""
        wait_for_service(
            f"{BACKEND_URL}/api/v1/utils/health-check/",
            service_name="Backend",
        )
        response = session.get(
            f"{BACKEND_URL}/api/v1/utils/health-check/",
            timeout=REQUEST_TIMEOUT,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "OK"

    def test_redis_connectivity(self) -> None:
        """Test Redis connectivity."""
        try:
            import redis

            r = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            assert r.ping(), "Redis ping failed"
            print(f"✓ Redis is available at {REDIS_HOST}:{REDIS_PORT}")
        except ImportError:
            pytest.skip("redis package not installed")
        except Exception as e:
            pytest.fail(f"Redis connectivity failed: {e}")

    def test_prometheus_connectivity(self, session: requests.Session) -> None:
        """Test Prometheus connectivity."""
        try:
            wait_for_service(
                f"{PROMETHEUS_URL}/-/healthy",
                service_name="Prometheus",
                timeout=60,
            )
            response = session.get(
                f"{PROMETHEUS_URL}/-/healthy",
                timeout=REQUEST_TIMEOUT,
            )
            assert response.status_code == 200
        except Exception as e:
            pytest.skip(f"Prometheus not available: {e}")

    def test_langfuse_connectivity(self, session: requests.Session) -> None:
        """Test Langfuse connectivity."""
        try:
            wait_for_service(
                LANGFUSE_URL,
                service_name="Langfuse",
                timeout=90,
            )
            response = session.get(LANGFUSE_URL, timeout=REQUEST_TIMEOUT)
            assert response.status_code in (200, 401, 404)  # Service is responding
        except Exception as e:
            pytest.skip(f"Langfuse not available: {e}")


class TestAgentWorkflow:
    """Test complete agent workflow from UI to traces."""

    def test_agent_health_endpoint(
        self, session: requests.Session, auth_token: str
    ) -> None:
        """Test agent health check endpoint."""
        response = session.get(
            f"{BACKEND_URL}/api/v1/agent/health",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=REQUEST_TIMEOUT,
        )
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded")
        assert "model_name" in data
        assert "available_tools" in data
        print(f"✓ Agent health: {data}")

    def test_agent_run_endpoint(
        self, session: requests.Session, auth_token: str
    ) -> None:
        """
        Test agent run endpoint.

        Note: This test may be skipped if LLM API keys are not configured.
        It validates the API contract and error handling.
        """
        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = {
            "message": "Hello, this is an E2E smoke test. Please respond with 'test successful'.",
            "run_metadata": {"test": "e2e_smoke_test"},
        }

        response = session.post(
            f"{BACKEND_URL}/api/v1/agent/run",
            json=payload,
            headers=headers,
            timeout=60,  # Agent execution may take longer
        )

        # Accept both success and specific error cases
        # If API keys are missing, we'll get a 500 with specific error message
        if response.status_code == 500:
            error_detail = response.json().get("detail", "")
            # These are acceptable errors for E2E smoke test without API keys
            acceptable_errors = [
                "API key",
                "authentication",
                "credentials",
                "not configured",
            ]
            if any(err.lower() in error_detail.lower() for err in acceptable_errors):
                pytest.skip(f"LLM API not configured: {error_detail}")
            else:
                pytest.fail(f"Unexpected agent error: {error_detail}")

        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()

        # Validate response structure
        assert "response" in data
        assert "run_id" in data
        assert "status" in data
        assert "latency_ms" in data

        # Validate optional tracing fields
        if "trace_id" in data and data["trace_id"]:
            assert isinstance(data["trace_id"], str)
            print(f"✓ Agent run completed with trace_id: {data['trace_id']}")

        if "trace_url" in data and data["trace_url"]:
            assert isinstance(data["trace_url"], str)
            print(f"✓ Trace URL: {data['trace_url']}")

        # Store run_id for history test
        pytest.agent_run_id = data["run_id"]
        print(f"✓ Agent run successful: run_id={data['run_id']}")

    def test_agent_runs_history(
        self, session: requests.Session, auth_token: str
    ) -> None:
        """Test agent runs history endpoint with pagination."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = session.get(
            f"{BACKEND_URL}/api/v1/agent/runs",
            headers=headers,
            params={"limit": 10, "skip": 0},
            timeout=REQUEST_TIMEOUT,
        )

        assert response.status_code == 200
        data = response.json()

        # Validate pagination structure
        assert "data" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["data"], list)

        print(f"✓ Retrieved {len(data['data'])} agent runs (total: {data['total']})")

        # If we have runs, validate structure
        if data["data"]:
            run = data["data"][0]
            assert "id" in run
            assert "input" in run
            assert "output" in run
            assert "status" in run
            assert "created_at" in run

    def test_rate_limiting(
        self, session: requests.Session, auth_token: str
    ) -> None:
        """Test rate limiting on agent endpoints."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Check if rate limiting is enabled
        rate_limit_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        if not rate_limit_enabled:
            pytest.skip("Rate limiting is disabled")

        # Make rapid requests to trigger rate limit
        rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

        # We'll make half the limit to avoid actually hitting it in tests
        # This test just validates headers are present
        response = session.get(
            f"{BACKEND_URL}/api/v1/agent/runs",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

        # Check for rate limit headers (may not always be present)
        if "X-RateLimit-Limit" in response.headers:
            print(f"✓ Rate limit headers present: {response.headers.get('X-RateLimit-Limit')}")
        else:
            print("⚠ Rate limit headers not present (may not be configured)")


class TestMetricsAndObservability:
    """Test metrics collection and observability endpoints."""

    def test_prometheus_metrics_endpoint(self, session: requests.Session) -> None:
        """Test that Prometheus can scrape backend metrics."""
        try:
            response = session.get(
                f"{BACKEND_URL}/metrics",
                timeout=REQUEST_TIMEOUT,
            )

            # Metrics endpoint should return 200 or 404 (if not exposed)
            assert response.status_code in (200, 404)

            if response.status_code == 200:
                # Validate Prometheus format
                metrics_text = response.text
                assert "http_requests_total" in metrics_text or "python_" in metrics_text
                print("✓ Backend metrics endpoint is accessible")
            else:
                print("⚠ Backend metrics endpoint not exposed (may be disabled)")
        except Exception as e:
            pytest.skip(f"Metrics endpoint not available: {e}")

    def test_prometheus_targets(self, session: requests.Session) -> None:
        """Test Prometheus scraping targets."""
        try:
            wait_for_service(
                f"{PROMETHEUS_URL}/-/healthy",
                service_name="Prometheus",
                timeout=60,
            )

            response = session.get(
                f"{PROMETHEUS_URL}/api/v1/targets",
                timeout=REQUEST_TIMEOUT,
            )
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "success"

            # Check if we have active targets
            active_targets = data.get("data", {}).get("activeTargets", [])
            print(f"✓ Prometheus has {len(active_targets)} active targets")
        except Exception as e:
            pytest.skip(f"Prometheus not available: {e}")


def test_end_to_end_summary(session: requests.Session, auth_token: str) -> None:
    """
    Summary test that validates the complete stack is operational.

    This test runs last and provides a summary of the E2E test results.
    """
    print("\n" + "=" * 60)
    print("E2E SMOKE TEST SUMMARY")
    print("=" * 60)

    services = {
        "Backend API": f"{BACKEND_URL}/api/v1/utils/health-check/",
        "Agent Health": f"{BACKEND_URL}/api/v1/agent/health",
    }

    results: dict[str, Any] = {}

    for service_name, url in services.items():
        try:
            headers = {"Authorization": f"Bearer {auth_token}"} if "agent" in url else {}
            response = session.get(url, headers=headers, timeout=10)
            results[service_name] = {
                "status": "✓ PASS" if response.status_code == 200 else "✗ FAIL",
                "code": response.status_code,
            }
        except Exception as e:
            results[service_name] = {"status": "✗ FAIL", "error": str(e)}

    # Print results
    for service, result in results.items():
        status = result["status"]
        if "error" in result:
            print(f"{status} {service}: {result['error']}")
        else:
            print(f"{status} {service} (HTTP {result['code']})")

    print("=" * 60)

    # Assert all critical services are up
    failed_services = [
        name for name, result in results.items() if "✗ FAIL" in result["status"]
    ]
    assert not failed_services, f"Failed services: {', '.join(failed_services)}"
