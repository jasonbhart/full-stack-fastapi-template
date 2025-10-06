# Performance Testing Quick Start Guide

This guide shows you how to run performance tests for the Unified FastAPI LLM Template.

## Prerequisites

1. **Backend must be running**:
   ```bash
   # Option 1: Docker Compose
   docker compose up -d backend db redis

   # Option 2: Local development
   cd backend
   uv run fastapi dev app/main.py
   ```

2. **Python dependencies**:
   ```bash
   # Installed automatically by the test runner, or manually:
   pip install httpx colorama
   ```

## Quick Start

### Run Full Performance Test Suite

```bash
# From project root
./scripts/run_performance_tests.sh
```

This will:
- Test backend availability
- Run 30-second load test with 10 concurrent users
- Monitor CPU and memory usage
- Test rate limiting behavior
- Generate detailed reports

**Output**:
- Performance results: `./performance_results/perf_test_TIMESTAMP.log`
- Resource usage: `./performance_results/resources_TIMESTAMP.json`

### Custom Test Configurations

#### Short Test (Quick Validation)
```bash
DURATION=10 CONCURRENCY=5 ./scripts/run_performance_tests.sh
```

#### Stress Test (High Load)
```bash
DURATION=60 CONCURRENCY=50 ./scripts/run_performance_tests.sh
```

#### Extended Test (Sustained Load)
```bash
DURATION=300 CONCURRENCY=20 ./scripts/run_performance_tests.sh
```

#### Different Backend URL
```bash
BACKEND_URL=http://api.example.com ./scripts/run_performance_tests.sh
```

## Individual Test Tools

### 1. Performance/Load Testing

Test agent endpoint performance and rate limiting:

```bash
# Standard load test
python3 scripts/performance_test.py \
    --base-url http://localhost:8000 \
    --concurrency 10 \
    --duration 30

# High concurrency test
python3 scripts/performance_test.py --concurrency 50 --duration 60

# Rate limiting test only
python3 scripts/performance_test.py --rate-limit-only

# Custom credentials
python3 scripts/performance_test.py \
    --email user@example.com \
    --password mypassword
```

**Options**:
- `--base-url URL`: API base URL (default: http://localhost:8000)
- `--concurrency N`: Number of concurrent workers (default: 10)
- `--duration N`: Test duration in seconds (default: 30)
- `--email`: Login email (default: admin@example.com)
- `--password`: Login password (default: changethisnowplease)
- `--rate-limit-only`: Only test rate limiting

### 2. Resource Monitoring

Monitor CPU, memory, and Docker container resources:

```bash
# Basic monitoring (30 seconds)
python3 scripts/monitor_resources.py

# Custom duration and interval
python3 scripts/monitor_resources.py --duration 60 --interval 2

# Save results to file
python3 scripts/monitor_resources.py --output resources.json
```

**Options**:
- `--duration N`: Monitoring duration in seconds (default: 30)
- `--interval N`: Measurement interval in seconds (default: 1)
- `--output FILE`: Save results to JSON file

## Understanding the Results

### Performance Test Output

```
================================================================================
Performance Test Results
================================================================================

Test Duration: 30.15 seconds
Total Requests: 1,234
Throughput: 40.93 req/s
Rate Limit Hits: 0

Response Time Statistics (seconds)
================================================================================
Endpoint             Count      Min        Max        Mean       P95        P99
================================================================================
agent_run            856        1.234      8.567      2.345      4.567      6.789
get_runs             234        0.045      0.234      0.089      0.156      0.198
health_check         144        0.012      0.098      0.034      0.067      0.089
================================================================================

Performance Assessment
================================================================================
Agent Run Performance: Good (mean: 2.35s)
Get Runs Performance:  Excellent (mean: 0.089s)
Health Check Performance: Excellent (mean: 0.034s)

Rate Limiting: Not triggered at this load level
================================================================================
```

### Key Metrics Explained

| Metric | Description | Good Value | Action Needed If |
|--------|-------------|------------|------------------|
| **Throughput** | Requests per second | 10-50 req/s | < 5 req/s: Check resources |
| **Agent Run Mean** | Average agent response time | < 5s | > 10s: Optimize or scale |
| **Agent Run P95** | 95th percentile response | < 10s | > 20s: Review traces |
| **Get Runs Mean** | Average history retrieval | < 100ms | > 500ms: Add indexes |
| **Rate Limit Hits** | Requests blocked by limits | Depends on config | > 50%: Increase limits |

### Resource Monitoring Output

```
================================================================================
Resource Usage Summary
================================================================================

full-stack-fastapi-project-backend-1
  CPU:    Avg:  25.50%  Min:  15.20%  Max:  45.80%
  Memory: Avg:   342MB  Min:   298MB  Max:   456MB
  Memory Usage: 34.2% of 1000MB

full-stack-fastapi-project-db-1
  CPU:    Avg:   8.30%  Min:   5.10%  Max:  18.40%
  Memory: Avg:   245MB  Min:   212MB  Max:   289MB
  Memory Usage: 24.5% of 1000MB

full-stack-fastapi-project-redis-1
  CPU:    Avg:   2.10%  Min:   1.20%  Max:   4.50%
  Memory: Avg:    45MB  Min:    42MB  Max:    52MB
  Memory Usage: 17.6% of 256MB
================================================================================
```

### Red Flags to Watch For

🚨 **Critical Issues**:
- Error rate > 5%
- Consistent timeouts
- CPU/Memory > 95%
- Service crashes

⚠️ **Warnings**:
- Agent mean response > 10s
- Error rate > 1%
- CPU/Memory > 80%
- High rate limit rejection rate

✅ **Healthy System**:
- Agent mean < 5s
- Error rate < 0.1%
- CPU/Memory < 70%
- Appropriate rate limiting

## Common Scenarios

### Scenario 1: Pre-Deployment Validation

```bash
# Quick sanity check before deployment
DURATION=30 CONCURRENCY=10 ./scripts/run_performance_tests.sh

# Review results
cat performance_results/perf_test_*.log | grep -A 5 "Performance Assessment"
```

**Expected**: All metrics in "Good" or "Excellent" range

### Scenario 2: Capacity Planning

```bash
# Test with expected peak load
DURATION=300 CONCURRENCY=50 ./scripts/run_performance_tests.sh

# Monitor resource usage closely
python3 scripts/monitor_resources.py --duration 300 --interval 5 --output capacity.json
```

**Goal**: Determine if current infrastructure can handle peak load

### Scenario 3: Rate Limiting Verification

```bash
# Test rate limiting specifically
python3 scripts/performance_test.py --rate-limit-only
```

**Expected**: Should see rate limiting kick in around configured threshold

### Scenario 4: Regression Testing

```bash
# Before making changes
./scripts/run_performance_tests.sh
mv performance_results/perf_test_*.log baseline_before.log

# After making changes
./scripts/run_performance_tests.sh
mv performance_results/perf_test_*.log baseline_after.log

# Compare results
diff baseline_before.log baseline_after.log
```

**Goal**: Ensure changes didn't degrade performance

## Troubleshooting

### Backend Not Available

**Error**: `Backend is not available at http://localhost:8000`

**Solution**:
```bash
# Check if services are running
docker compose ps

# Start backend
docker compose up -d backend db redis

# Wait for backend to be ready (check health)
curl http://localhost:8000/api/v1/agent/health
```

### Authentication Failed

**Error**: `Failed to authenticate. Check credentials.`

**Solutions**:
1. Check `.env` file for correct credentials
2. Verify superuser exists:
   ```bash
   docker compose exec backend uv run python -c "
   from app.core.db import engine
   from sqlmodel import Session, select
   from app.models import User
   with Session(engine) as session:
       user = session.exec(select(User).where(User.email == 'admin@example.com')).first()
       print(f'User exists: {user is not None}')
   "
   ```
3. Use correct credentials in test:
   ```bash
   python3 scripts/performance_test.py \
       --email your@email.com \
       --password yourpassword
   ```

### High Error Rate

**Symptom**: Many errors in test results

**Diagnosis**:
```bash
# Check backend logs
docker compose logs backend --tail 100

# Check for specific errors
docker compose logs backend | grep -i "error\|exception"
```

**Common Causes**:
- Database connection issues
- LLM API key invalid/missing
- Rate limiting too aggressive
- Memory exhaustion

### Dependencies Missing

**Error**: `ModuleNotFoundError: No module named 'httpx'`

**Solution**:
```bash
# Install dependencies
cd backend
uv pip install httpx colorama

# Or use system pip
pip install httpx colorama
```

## Performance Optimization

If tests show poor performance, see the main [Performance Documentation](PERFORMANCE.md) for:

- Bottleneck analysis
- Optimization recommendations
- Scaling guidelines
- Production deployment tips

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Performance Tests

on:
  push:
    branches: [master]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - name: Start services
        run: docker compose up -d backend db redis
      - name: Wait for backend
        run: |
          timeout 60 bash -c 'until curl -sf http://localhost:8000/docs; do sleep 2; done'
      - name: Run performance tests
        run: |
          DURATION=60 CONCURRENCY=20 ./scripts/run_performance_tests.sh
      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: performance-results
          path: performance_results/
```

## Best Practices

1. **Run tests regularly**: Weekly or before major deployments
2. **Establish baselines**: Save first test results as baseline
3. **Test realistic scenarios**: Match expected production load
4. **Monitor over time**: Track performance trends
5. **Test with rate limiting**: Ensure it works as expected
6. **Check resource usage**: Ensure infrastructure is adequate
7. **Review Langfuse traces**: Identify slow LLM calls
8. **Document results**: Keep records of test outcomes

## Next Steps

After running performance tests:

1. Review the [Full Performance Documentation](PERFORMANCE.md)
2. Check [Prometheus Metrics](http://localhost:8000/metrics)
3. Analyze [Langfuse Traces](https://cloud.langfuse.com)
4. Review [Grafana Dashboards](http://localhost:3000) (if configured)
5. Optimize based on findings
6. Re-test after optimizations

## Support

For issues or questions:
- Check [PERFORMANCE.md](PERFORMANCE.md) for detailed guidance
- Review backend logs: `docker compose logs backend`
- Check system resources: `docker stats`
- Open an issue on GitHub with test results attached

---

**Remember**: Performance testing is an ongoing process, not a one-time activity. Regular testing helps catch regressions early and ensures your system scales with growth.
