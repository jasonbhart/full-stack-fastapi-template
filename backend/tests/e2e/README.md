# End-to-End Smoke Tests

This directory contains end-to-end (E2E) smoke tests for the Full Stack FastAPI Template with LLM agent capabilities.

## Overview

The E2E smoke tests validate the complete system integration, including:
- **Service Connectivity**: All Docker services are up and responding
- **Backend API**: Health checks and authentication
- **Agent Workflow**: Complete agent execution from API to database
- **Observability**: Langfuse tracing, Prometheus metrics
- **Rate Limiting**: Redis-based rate limiting functionality

## Quick Start

### Run E2E Tests

From the project root:

```bash
# Run complete E2E test suite (starts services, runs tests, cleans up)
./scripts/test_e2e.sh

# Skip building Docker images
./scripts/test_e2e.sh --skip-build

# Keep services running after tests (for debugging)
./scripts/test_e2e.sh --keep-running

# Verbose output
./scripts/test_e2e.sh --verbose
```

### Run Tests Manually

If services are already running:

```bash
cd backend

# With uv (recommended) - clear default filter and select E2E tests
uv run pytest --override-ini addopts= -m e2e tests/e2e/test_agent_flow.py -v

# Or with pytest directly
pytest --override-ini addopts= -m e2e tests/e2e/test_agent_flow.py -v

# Run all E2E tests
uv run pytest --override-ini addopts= -m e2e -v
```

**Note**: E2E tests are excluded by default via `addopts = "-m 'not e2e'"` in `pyproject.toml`. To run them, you must:
1. Clear the default filter with `--override-ini addopts=`
2. Then select E2E tests with `-m e2e`

## Why E2E Tests Are Excluded by Default

E2E tests require the full Docker Compose stack to be running, including:
- PostgreSQL database
- Redis cache
- Backend API server
- Optional: Langfuse, Prometheus, Grafana

Running these tests as part of the regular unit/integration test suite would:
- Significantly increase test execution time
- Fail in environments where Docker isn't available
- Require additional setup before running tests

Therefore:
- **Default behavior** (`pytest tests/`): E2E tests are automatically excluded
- **E2E execution**: Use `./scripts/test_e2e.sh` (recommended) or manually with `--override-ini addopts= -m e2e`
- **CI/CD**: Regular test commands automatically exclude E2E tests

## Test Structure

### `test_agent_flow.py`

Main E2E test module with the following test classes:

#### TestServiceConnectivity
- **test_backend_health**: Validates backend API health endpoint
- **test_redis_connectivity**: Checks Redis connection for rate limiting
- **test_prometheus_connectivity**: Verifies Prometheus is accessible
- **test_langfuse_connectivity**: Validates Langfuse observability platform

#### TestAgentWorkflow
- **test_agent_health_endpoint**: Checks agent service health
- **test_agent_run_endpoint**: Executes complete agent workflow
- **test_agent_runs_history**: Validates pagination and history retrieval
- **test_rate_limiting**: Verifies rate limit headers and functionality

#### TestMetricsAndObservability
- **test_prometheus_metrics_endpoint**: Validates metrics exposure
- **test_prometheus_targets**: Checks Prometheus scraping configuration

#### Summary Test
- **test_end_to_end_summary**: Provides comprehensive test summary

## Configuration

### Environment Variables

The E2E tests can be configured with the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `E2E_BACKEND_URL` | `http://localhost:8000` | Backend API URL |
| `E2E_LANGFUSE_URL` | `http://localhost:3000` | Langfuse URL |
| `E2E_PROMETHEUS_URL` | `http://localhost:9090` | Prometheus URL |
| `E2E_GRAFANA_URL` | `http://localhost:3001` | Grafana URL |
| `E2E_REDIS_HOST` | `localhost` | Redis host |
| `E2E_REDIS_PORT` | `6379` | Redis port |
| `E2E_STARTUP_TIMEOUT` | `180` | Service startup timeout (seconds) |
| `E2E_REQUEST_TIMEOUT` | `30` | HTTP request timeout (seconds) |
| `E2E_CLEANUP` | `true` | Clean up services after tests |

### Credentials

Tests use the following credentials from `.env`:

- `FIRST_SUPERUSER`: Admin email (default: `admin@example.com`)
- `FIRST_SUPERUSER_PASSWORD`: Admin password (default: `changethis`)

## Test Behavior

### Graceful Degradation

The tests are designed to handle missing or unavailable services gracefully:

- **Optional Services**: Tests for Langfuse, Prometheus, and Grafana will be skipped if services are unavailable
- **API Keys**: Agent run tests will be skipped if LLM API keys are not configured
- **Rate Limiting**: Rate limit tests will be skipped if rate limiting is disabled

This allows the tests to validate core functionality even in minimal configurations.

### Idempotency

The test suite is idempotent and can be run multiple times:

- Each test run uses a separate Docker Compose project (`fastapi-e2e-test`)
- Services are cleaned up after tests (unless `--keep-running` is used)
- Database state is isolated per test run

## CI/CD Integration

The E2E test suite is designed for CI/CD environments:

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up environment
        run: cp .env.example .env

      - name: Run E2E tests
        run: ./scripts/test_e2e.sh
        env:
          FIRST_SUPERUSER: admin@example.com
          FIRST_SUPERUSER_PASSWORD: testpassword123
```

### GitLab CI Example

```yaml
e2e-tests:
  stage: test
  image: docker:latest
  services:
    - docker:dind
  before_script:
    - cp .env.example .env
  script:
    - ./scripts/test_e2e.sh
  variables:
    FIRST_SUPERUSER: admin@example.com
    FIRST_SUPERUSER_PASSWORD: testpassword123
```

## Debugging

### View Service Logs

```bash
# All services
docker compose -p fastapi-e2e-test logs -f

# Specific service
docker compose -p fastapi-e2e-test logs -f backend

# Last 100 lines
docker compose -p fastapi-e2e-test logs --tail=100
```

### Keep Services Running

```bash
# Run tests but keep services running
./scripts/test_e2e.sh --keep-running

# Then inspect services
docker compose -p fastapi-e2e-test ps
docker compose -p fastapi-e2e-test exec backend bash

# When done, clean up
docker compose -p fastapi-e2e-test down -v
```

### Run Individual Tests

```bash
cd backend

# Run specific test class
uv run pytest --override-ini addopts= -m e2e tests/e2e/test_agent_flow.py::TestAgentWorkflow -v

# Run specific test
uv run pytest --override-ini addopts= -m e2e tests/e2e/test_agent_flow.py::TestAgentWorkflow::test_agent_health_endpoint -v

# Run with debug output
uv run pytest --override-ini addopts= -m e2e tests/e2e/test_agent_flow.py -v -s
```

## Troubleshooting

### Services Not Starting

1. Check Docker daemon is running: `docker info`
2. Verify `.env` file exists and is valid
3. Check port conflicts: `docker compose -p fastapi-e2e-test ps`
4. View service logs: `docker compose -p fastapi-e2e-test logs`

### Tests Timing Out

1. Increase timeout: `E2E_STARTUP_TIMEOUT=300 ./scripts/test_e2e.sh`
2. Check service health: `docker compose -p fastapi-e2e-test ps`
3. Verify network connectivity: `docker compose -p fastapi-e2e-test exec backend curl http://db:5432`

### Rate Limiting Issues

1. Check Redis is running: `docker compose -p fastapi-e2e-test ps redis`
2. Verify Redis connectivity: `docker compose -p fastapi-e2e-test exec backend redis-cli -h redis ping`
3. Disable rate limiting for tests: Set `RATE_LIMIT_ENABLED=false` in `.env`

## Extending Tests

### Adding New Test Cases

1. Create new test method in appropriate class
2. Use fixtures for authentication and session management
3. Follow naming convention: `test_<feature>_<scenario>`
4. Add docstring explaining test purpose

Example:

```python
def test_new_feature(self, session: requests.Session, auth_token: str) -> None:
    """Test description of what this validates."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = session.get(
        f"{BACKEND_URL}/api/v1/new-endpoint",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 200
    # Additional assertions
```

### Adding New Services

1. Update service connectivity tests
2. Add environment variable configuration
3. Implement graceful skip if service unavailable
4. Update documentation

## Best Practices

1. **Always use fixtures** for authentication and session management
2. **Handle missing services gracefully** with pytest.skip()
3. **Validate response structure**, not just status codes
4. **Use meaningful assertions** with descriptive messages
5. **Add logging** for debugging complex scenarios
6. **Keep tests fast** - use timeouts appropriately
7. **Make tests independent** - don't rely on test order
8. **Clean up resources** - use fixtures for setup/teardown

## Related Documentation

- [Backend API Documentation](../../../docs/api.md)
- [Agent Architecture](../../../docs/architecture/llm-agents.md)
- [Docker Deployment](../../../docs/deployment.md)
- [Main README](../../../README.md)
