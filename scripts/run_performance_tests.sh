#!/bin/bash
set -e
set -o pipefail

# Performance Test Runner
# Runs performance tests with resource monitoring

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
CONCURRENCY="${CONCURRENCY:-10}"
DURATION="${DURATION:-30}"
OUTPUT_DIR="${OUTPUT_DIR:-./performance_results}"

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}Performance Test Suite${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo -e "Backend URL:  ${BACKEND_URL}"
echo -e "Concurrency:  ${CONCURRENCY}"
echo -e "Duration:     ${DURATION}s"
echo -e "Output Dir:   ${OUTPUT_DIR}"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RESULT_FILE="$OUTPUT_DIR/perf_test_${TIMESTAMP}.log"
RESOURCE_FILE="$OUTPUT_DIR/resources_${TIMESTAMP}.json"

# Check if backend is running
echo -e "${YELLOW}Checking backend availability...${NC}"
if ! curl -s --fail "${BACKEND_URL}/docs" > /dev/null 2>&1; then
    echo -e "${RED}✗ Backend is not available at ${BACKEND_URL}${NC}"
    echo -e "${YELLOW}Please start the backend first:${NC}"
    echo -e "  docker compose up -d backend"
    echo -e "  OR"
    echo -e "  cd backend && fastapi dev app/main.py"
    exit 1
fi
echo -e "${GREEN}✓ Backend is available${NC}"
echo ""

# Check if required Python packages are installed
echo -e "${YELLOW}Checking dependencies...${NC}"
cd "$(dirname "$0")/.."
if ! python3 -c "import httpx, colorama" 2>/dev/null; then
    echo -e "${YELLOW}Installing required packages...${NC}"
    if command -v uv &> /dev/null; then
        (cd backend && uv pip install httpx colorama)
    else
        pip install httpx colorama
    fi
fi
echo -e "${GREEN}✓ Dependencies ready${NC}"
echo ""

# Start resource monitoring in background
echo -e "${YELLOW}Starting resource monitor...${NC}"
python3 scripts/monitor_resources.py \
    --duration "$((DURATION + 10))" \
    --interval 2 \
    --output "$RESOURCE_FILE" > /dev/null 2>&1 &
MONITOR_PID=$!
echo -e "${GREEN}✓ Resource monitor started (PID: $MONITOR_PID)${NC}"
echo ""

# Wait a moment for monitor to start
sleep 2

# Run performance tests
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}Running Performance Tests${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

python3 scripts/performance_test.py \
    --base-url "$BACKEND_URL" \
    --concurrency "$CONCURRENCY" \
    --duration "$DURATION" | tee "$RESULT_FILE"

# Wait for resource monitor to finish
echo -e "${YELLOW}Waiting for resource monitor to complete...${NC}"
wait $MONITOR_PID 2>/dev/null || true
echo ""

# Summary
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}Test Complete${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e "Results saved to:"
echo -e "  Performance: ${GREEN}${RESULT_FILE}${NC}"
echo -e "  Resources:   ${GREEN}${RESOURCE_FILE}${NC}"
echo ""

# Quick analysis
if [ -f "$RESULT_FILE" ]; then
    echo -e "${CYAN}Quick Analysis:${NC}"

    # Extract throughput
    THROUGHPUT=$(grep "Throughput:" "$RESULT_FILE" | awk '{print $2}' | head -1)
    if [ ! -z "$THROUGHPUT" ]; then
        echo -e "  Throughput: ${GREEN}${THROUGHPUT}${NC}"
    fi

    # Extract rate limit hits
    RATE_LIMITS=$(grep "Rate Limit Hits:" "$RESULT_FILE" | awk '{print $4}' | head -1)
    if [ ! -z "$RATE_LIMITS" ]; then
        if [ "$RATE_LIMITS" -gt 0 ]; then
            echo -e "  Rate Limits: ${YELLOW}${RATE_LIMITS} hits${NC}"
        else
            echo -e "  Rate Limits: ${GREEN}None${NC}"
        fi
    fi

    echo ""
fi

echo -e "${GREEN}✓ Performance testing complete${NC}"
echo ""
