#!/usr/bin/env bash

#
# End-to-End Smoke Test Script
#
# This script spins up the full Docker Compose stack, runs E2E tests,
# and cleans up afterward. It's designed to be idempotent and suitable
# for CI/CD environments.
#
# Usage:
#   ./scripts/test_e2e.sh [options]
#
# Options:
#   --skip-build    Skip building Docker images
#   --keep-running  Don't stop services after tests
#   --verbose       Enable verbose output
#   --help          Show this help message
#
# Environment Variables:
#   E2E_BACKEND_URL       Backend URL (default: http://localhost:8000)
#   E2E_STARTUP_TIMEOUT   Service startup timeout in seconds (default: 180)
#   E2E_CLEANUP           Clean up services after tests (default: true)
#

set -e  # Exit on error
set -u  # Exit on undefined variable

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default configuration
SKIP_BUILD=false
KEEP_RUNNING=false
VERBOSE=false
CLEANUP="${E2E_CLEANUP:-true}"
COMPOSE_PROJECT_NAME="fastapi-e2e-test"

# Test configuration
BACKEND_URL="${E2E_BACKEND_URL:-http://localhost:8000}"
STARTUP_TIMEOUT="${E2E_STARTUP_TIMEOUT:-180}"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --keep-running)
            KEEP_RUNNING=true
            CLEANUP=false
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            grep '^#' "$0" | grep -v '#!/usr/bin/env' | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Cleanup function
cleanup() {
    local exit_code=$?

    if [[ "$CLEANUP" == "true" ]]; then
        log_info "Cleaning up Docker Compose stack..."
        cd "$PROJECT_ROOT"
        docker compose -p "$COMPOSE_PROJECT_NAME" down -v --remove-orphans 2>/dev/null || true
        log_success "Cleanup complete"
    else
        log_info "Skipping cleanup (services kept running)"
    fi

    exit $exit_code
}

# Set up cleanup trap
trap cleanup EXIT INT TERM

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if docker is available
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi

    # Check if docker compose is available
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed or not available"
        exit 1
    fi

    # Check if .env file exists
    if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
        log_warning ".env file not found, copying from .env.example"
        if [[ -f "$PROJECT_ROOT/.env.example" ]]; then
            cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        else
            log_error ".env.example not found, cannot create .env"
            exit 1
        fi
    fi

    log_success "Prerequisites check passed"
}

# Wait for service to be healthy
wait_for_service() {
    local service_name=$1
    local url=$2
    local timeout=${3:-$STARTUP_TIMEOUT}
    local elapsed=0
    local interval=5

    log_info "Waiting for $service_name to be ready at $url..."

    while [[ $elapsed -lt $timeout ]]; do
        if curl -f -s -o /dev/null "$url"; then
            log_success "$service_name is ready"
            return 0
        fi

        sleep $interval
        elapsed=$((elapsed + interval))

        if [[ $((elapsed % 20)) -eq 0 ]]; then
            log_info "Still waiting for $service_name... (${elapsed}s elapsed)"
        fi
    done

    log_error "$service_name did not become ready within ${timeout}s"
    return 1
}

# Start Docker Compose stack
start_stack() {
    log_info "Starting Docker Compose stack..."
    cd "$PROJECT_ROOT"

    # Set environment for E2E testing
    export COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME"

    # Build if needed
    if [[ "$SKIP_BUILD" == "false" ]]; then
        log_info "Building Docker images..."
        docker compose -p "$COMPOSE_PROJECT_NAME" build
    fi

    # Start services
    log_info "Starting services..."
    if [[ "$VERBOSE" == "true" ]]; then
        docker compose -p "$COMPOSE_PROJECT_NAME" up -d
    else
        docker compose -p "$COMPOSE_PROJECT_NAME" up -d > /dev/null 2>&1
    fi

    log_success "Docker Compose stack started"
}

# Wait for all services
wait_for_services() {
    log_info "Waiting for services to be ready..."

    # Wait for backend (most critical)
    wait_for_service "Backend API" "$BACKEND_URL/api/v1/utils/health-check/" || {
        log_error "Backend API failed to start. Showing logs:"
        docker compose -p "$COMPOSE_PROJECT_NAME" logs backend
        return 1
    }

    # Optional: wait for other services (but don't fail if they're not available)
    # This allows the tests to skip optional services gracefully
    log_info "Core services are ready. Optional services will be checked during tests."
}

# Run E2E tests
run_tests() {
    log_info "Running E2E tests..."
    cd "$PROJECT_ROOT/backend"

    # Set environment variables for tests
    export E2E_BACKEND_URL="$BACKEND_URL"
    export E2E_STARTUP_TIMEOUT="$STARTUP_TIMEOUT"

    # Check if we should run tests in Docker or locally
    # Note: We override addopts to clear the default "-m 'not e2e'" filter
    if command -v uv &> /dev/null && [[ -d ".venv" ]]; then
        # Run tests locally with uv
        log_info "Running tests with local uv environment..."
        uv run pytest --override-ini addopts= -m e2e tests/e2e/test_agent_flow.py -v --tb=short
    elif command -v pytest &> /dev/null; then
        # Run tests with system pytest
        log_info "Running tests with system pytest..."
        pytest --override-ini addopts= -m e2e tests/e2e/test_agent_flow.py -v --tb=short
    else
        # Run tests inside the backend container
        log_info "Running tests inside backend container..."
        cd "$PROJECT_ROOT"
        docker compose -p "$COMPOSE_PROJECT_NAME" exec -T backend \
            pytest --override-ini addopts= -m e2e tests/e2e/test_agent_flow.py -v --tb=short
    fi

    local test_exit_code=$?

    if [[ $test_exit_code -eq 0 ]]; then
        log_success "All E2E tests passed!"
    else
        log_error "E2E tests failed with exit code $test_exit_code"
        return $test_exit_code
    fi
}

# Show service status
show_status() {
    log_info "Service status:"
    cd "$PROJECT_ROOT"
    docker compose -p "$COMPOSE_PROJECT_NAME" ps
}

# Main execution
main() {
    log_info "==================================================="
    log_info "  Full Stack FastAPI - E2E Smoke Test Suite"
    log_info "==================================================="
    echo ""

    # Run checks and setup
    check_prerequisites

    # Start stack
    start_stack

    # Wait for services
    wait_for_services

    # Show service status
    show_status

    echo ""
    log_info "==================================================="
    log_info "  Running E2E Tests"
    log_info "==================================================="
    echo ""

    # Run tests
    run_tests
    test_result=$?

    echo ""
    log_info "==================================================="
    log_info "  E2E Test Suite Complete"
    log_info "==================================================="

    if [[ $test_result -eq 0 ]]; then
        log_success "All tests passed successfully! ✓"
    else
        log_error "Some tests failed. Check output above for details."
    fi

    if [[ "$KEEP_RUNNING" == "true" ]]; then
        echo ""
        log_info "Services are still running. Use the following commands:"
        log_info "  - View logs: docker compose -p $COMPOSE_PROJECT_NAME logs -f"
        log_info "  - Stop services: docker compose -p $COMPOSE_PROJECT_NAME down"
    fi

    return $test_result
}

# Run main function
main
