#!/usr/bin/env bash

set -e
set -x

# Disable rate limiting for tests to avoid interference between tests
export RATE_LIMIT_ENABLED=false

# E2E tests are excluded by default via pyproject.toml addopts
# To run E2E tests, use: ./scripts/test_e2e.sh
coverage run -m pytest tests/
coverage report
coverage html --title "${@-coverage}"
