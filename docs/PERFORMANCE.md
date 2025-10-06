# Performance Characteristics and Optimization Guide

This document describes the performance characteristics of the Unified FastAPI LLM Template, including benchmark results, optimization recommendations, and monitoring guidelines.

## Overview

The template is designed to handle production workloads with:
- **Agent endpoints**: AI-powered conversational interactions
- **CRUD endpoints**: Traditional REST API operations
- **Rate limiting**: Protection against abuse
- **Observability**: Comprehensive monitoring and tracing

## Performance Testing

### Test Tools

The template includes comprehensive performance testing tools:

1. **`scripts/performance_test.py`** - Load testing for agent endpoints
   - Concurrent request handling
   - Response time measurement
   - Rate limiting validation
   - Throughput analysis

2. **`scripts/monitor_resources.py`** - Resource monitoring
   - CPU usage tracking
   - Memory consumption
   - Container resource monitoring
   - Real-time statistics

3. **`scripts/run_performance_tests.sh`** - Orchestration script
   - Automated test execution
   - Combined performance and resource monitoring
   - Result aggregation

### Running Performance Tests

#### Quick Test (30 seconds, 10 concurrent users)
```bash
./scripts/run_performance_tests.sh
```

#### Extended Test (60 seconds, 25 concurrent users)
```bash
DURATION=60 CONCURRENCY=25 ./scripts/run_performance_tests.sh
```

#### Custom Configuration
```bash
# Set environment variables
export BACKEND_URL=http://localhost:8000
export CONCURRENCY=20
export DURATION=120
export OUTPUT_DIR=./my_results

# Run tests
./scripts/run_performance_tests.sh
```

#### Direct Python Execution
```bash
# Load test only
python3 scripts/performance_test.py --concurrency 15 --duration 45

# Rate limiting test only
python3 scripts/performance_test.py --rate-limit-only

# Resource monitoring
python3 scripts/monitor_resources.py --duration 60 --interval 2 --output results.json
```

## Baseline Performance Characteristics

### Test Environment Specifications
- **Platform**: Linux 5.15.0-156-generic
- **Python**: 3.11
- **Database**: PostgreSQL 13+
- **Deployment**: Docker Compose (development mode)

### Agent Endpoint Performance

#### `/api/v1/agent/run` (POST)
**Description**: Execute agent with LLM processing

| Metric | Target | Typical Range | Notes |
|--------|--------|---------------|-------|
| Response Time (Mean) | < 5s | 1.5 - 8s | Depends on LLM provider latency |
| Response Time (P95) | < 10s | 3 - 15s | Includes tool execution time |
| Response Time (P99) | < 15s | 5 - 20s | May include retries |
| Throughput | 5-20 req/s | Varies | Limited by LLM API rate limits |

**Performance Factors**:
- **LLM Provider**: OpenAI, Anthropic, Azure have different latencies
- **Tool Execution**: Database lookups add 50-200ms per tool call
- **Message Length**: Longer messages increase processing time
- **Tracing Overhead**: Langfuse adds ~50-100ms per request

**Optimization Tips**:
1. Use streaming responses for better user experience
2. Cache common queries at application level
3. Use faster LLM models for simple queries (e.g., gpt-3.5-turbo)
4. Implement request queuing for burst traffic

#### `/api/v1/agent/runs` (GET)
**Description**: Retrieve agent run history with pagination

| Metric | Target | Typical Range | Notes |
|--------|--------|---------------|-------|
| Response Time (Mean) | < 100ms | 50-200ms | Depends on database load |
| Response Time (P95) | < 250ms | 100-400ms | Includes pagination |
| Response Time (P99) | < 500ms | 200-600ms | Large result sets |
| Throughput | 50-200 req/s | Varies | Database-bound |

**Optimization Tips**:
1. Ensure indexes on `user_id`, `created_at`, `trace_id` exist
2. Use appropriate page sizes (default: 10-50 items)
3. Consider caching for frequently accessed pages
4. Monitor database connection pool size

#### `/api/v1/agent/health` (GET)
**Description**: Health check endpoint (no authentication required)

| Metric | Target | Typical Range | Notes |
|--------|--------|---------------|-------|
| Response Time (Mean) | < 50ms | 10-80ms | Minimal processing |
| Response Time (P95) | < 100ms | 30-150ms | Includes Langfuse check |
| Response Time (P99) | < 200ms | 50-250ms | Network variability |
| Throughput | 100-500 req/s | Varies | Lightweight endpoint |

### CRUD Endpoint Performance

Traditional CRUD endpoints (users, items) typically perform better than agent endpoints:

| Endpoint Type | Mean Response Time | P95 | Throughput |
|---------------|-------------------|-----|------------|
| Simple GET | 10-50ms | 50-100ms | 200-500 req/s |
| GET with joins | 20-100ms | 100-200ms | 100-300 req/s |
| POST/PUT | 30-150ms | 150-300ms | 50-200 req/s |
| DELETE | 20-80ms | 80-150ms | 100-300 req/s |

## Rate Limiting

### Configuration

Rate limiting is controlled by environment variables:

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60  # Requests per minute per user
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Performance Impact

Rate limiting adds minimal overhead:
- **Additional latency**: ~5-15ms per request
- **Redis memory**: ~1KB per active user
- **Redis operations**: 2-3 operations per request (GET, INCR, EXPIRE)

### Testing Rate Limits

```bash
# Test rate limiting specifically
python3 scripts/performance_test.py --rate-limit-only

# Monitor rate limit hits during load test
./scripts/run_performance_tests.sh
```

### Tuning Recommendations

1. **Low traffic** (< 10 users): 60 req/min per user
2. **Medium traffic** (10-100 users): 30 req/min per user
3. **High traffic** (100+ users): 15 req/min per user
4. **API keys/services**: Consider separate, higher limits

## Resource Usage

### Memory Consumption

**Backend Container (per worker)**:
- Base memory: 150-250 MB
- Per agent request: +50-100 MB (temporary, garbage collected)
- Peak memory: 400-600 MB under load
- Recommended: 1GB allocated per worker

**Database Container**:
- Base memory: 100-200 MB
- Per connection: +2-5 MB
- Working set: 256-512 MB
- Recommended: 1-2GB allocated

**Redis Container**:
- Base memory: 10-20 MB
- Per active user: ~1 KB
- Cache data: Varies
- Recommended: 256MB allocated

### CPU Utilization

**Typical Usage** (10 concurrent users):
- Backend: 15-30% CPU
- Database: 5-15% CPU
- Redis: 1-5% CPU

**Under Load** (50 concurrent users):
- Backend: 50-80% CPU
- Database: 20-40% CPU
- Redis: 5-10% CPU

**CPU Optimization**:
1. Use uvicorn with multiple workers: `--workers 4`
2. Optimize database queries (avoid N+1 queries)
3. Enable query result caching
4. Use connection pooling

## Monitoring and Observability

### Prometheus Metrics

Key metrics exposed at `/metrics`:

```
# Agent-specific metrics
agent_invocations_total
agent_invocations_current
agent_request_duration_seconds
agent_status_total{status="success|error|rate_limited"}
agent_tokens_total{type="input|output"}

# HTTP metrics (auto-instrumented)
http_requests_total
http_request_duration_seconds
http_requests_in_progress

# System metrics
process_cpu_seconds_total
process_resident_memory_bytes
```

### Langfuse Tracing

All agent requests are traced in Langfuse:
- **Trace ID**: Unique identifier for each agent run
- **Spans**: Individual LLM calls, tool executions
- **Metadata**: User ID, thread ID, custom metadata
- **Costs**: Token usage and estimated cost

### Logging

Structured JSON logs include:
- **correlation_id**: Request correlation
- **trace_id**: Langfuse trace ID
- **Response times**: Logged at INFO level
- **Errors**: Logged at ERROR level with stack traces

## Bottleneck Analysis

### Common Bottlenecks

1. **LLM API Latency** (Most Common)
   - **Symptom**: High P95/P99 response times
   - **Solution**: Use streaming, cache responses, use faster models

2. **Database Queries**
   - **Symptom**: Slow `/agent/runs` endpoint
   - **Solution**: Add indexes, optimize queries, connection pooling

3. **Rate Limiting Redis**
   - **Symptom**: Increased latency on all requests
   - **Solution**: Use Redis cluster, increase Redis resources

4. **Memory Pressure**
   - **Symptom**: High GC pauses, OOM errors
   - **Solution**: Increase container memory, reduce concurrent workers

5. **Langfuse Tracing**
   - **Symptom**: ~100ms overhead per request
   - **Solution**: Reduce sampling rate, use async flushing

### Identifying Bottlenecks

```bash
# Run performance test with resource monitoring
./scripts/run_performance_tests.sh

# Check Prometheus metrics
curl http://localhost:8000/metrics

# View Langfuse traces
# Visit Langfuse dashboard for detailed trace analysis

# Check Docker stats
docker stats

# View application logs
docker compose logs backend | grep -i "slow\|timeout\|error"
```

## Optimization Checklist

### Application Level
- [ ] Enable response streaming for agent endpoints
- [ ] Implement query result caching (Redis)
- [ ] Use database connection pooling (configured)
- [ ] Optimize database queries (add indexes)
- [ ] Use appropriate LLM models (balance speed vs quality)
- [ ] Enable compression for API responses
- [ ] Implement request queuing for burst traffic

### Infrastructure Level
- [ ] Use multiple uvicorn workers (`--workers 4`)
- [ ] Allocate sufficient memory (1GB+ per backend worker)
- [ ] Use PostgreSQL query optimization (EXPLAIN ANALYZE)
- [ ] Configure Redis persistence appropriately
- [ ] Enable HTTP/2 in production (Traefik)
- [ ] Use CDN for static assets (if applicable)
- [ ] Implement database read replicas for high read load

### Monitoring
- [ ] Set up Prometheus alerts for high latency
- [ ] Monitor Langfuse trace success rates
- [ ] Track rate limiting hit rates
- [ ] Monitor database connection pool usage
- [ ] Set up error rate alerts
- [ ] Track token usage and costs
- [ ] Monitor container resource usage

## Performance Testing Best Practices

### Pre-Test Checklist
1. Ensure all services are healthy
2. Clear Redis cache if needed
3. Check database connection limits
4. Verify LLM API keys and quotas
5. Disable debug logging in production tests

### Test Scenarios

#### 1. Baseline Performance Test
```bash
# 10 concurrent users, 30 seconds
CONCURRENCY=10 DURATION=30 ./scripts/run_performance_tests.sh
```

#### 2. Stress Test
```bash
# 50 concurrent users, 60 seconds
CONCURRENCY=50 DURATION=60 ./scripts/run_performance_tests.sh
```

#### 3. Sustained Load Test
```bash
# 25 concurrent users, 5 minutes
CONCURRENCY=25 DURATION=300 ./scripts/run_performance_tests.sh
```

#### 4. Rate Limit Validation
```bash
python3 scripts/performance_test.py --rate-limit-only
```

### Interpreting Results

**Good Performance**:
- Agent runs: Mean < 5s, P95 < 10s
- Get runs: Mean < 100ms, P95 < 250ms
- Rate limiting working correctly
- No errors or timeouts
- CPU < 80%, Memory < 80%

**Needs Investigation**:
- Agent runs: Mean > 10s
- High error rates (> 1%)
- Many timeouts
- Rate limiting not triggering
- CPU/Memory > 90%

**Critical Issues**:
- Consistent timeouts
- Error rates > 5%
- Service crashes
- OOM kills
- Database connection exhaustion

## Production Deployment Recommendations

### Scaling Guidelines

**Small Deployment** (< 100 users):
- 2 backend workers
- 1 database instance (2GB RAM)
- 1 Redis instance (256MB RAM)
- Expected throughput: 10-20 agent requests/minute

**Medium Deployment** (100-1000 users):
- 4-8 backend workers
- 1 database instance (4-8GB RAM)
- 1 Redis instance (512MB-1GB RAM)
- Expected throughput: 50-100 agent requests/minute

**Large Deployment** (1000+ users):
- 8-16 backend workers (horizontal scaling)
- Database with read replicas
- Redis cluster
- CDN for static content
- Expected throughput: 200+ agent requests/minute

### Performance Monitoring in Production

1. **Set up continuous monitoring**:
   ```bash
   # Prometheus scrapes /metrics every 15s
   # Grafana dashboards for visualization
   # Langfuse for LLM trace analysis
   ```

2. **Configure alerts**:
   - Response time P95 > 15s
   - Error rate > 1%
   - CPU usage > 85%
   - Memory usage > 90%
   - Rate limiting hit rate > 10%

3. **Regular performance audits**:
   - Run performance tests weekly
   - Review Langfuse traces monthly
   - Optimize slow database queries
   - Update LLM models based on cost/performance

## Troubleshooting Performance Issues

### High Latency

**Symptoms**: Response times consistently > 10s

**Diagnosis**:
```bash
# Check Langfuse traces for slow spans
# Check Prometheus metrics for slow queries
curl http://localhost:8000/metrics | grep duration

# Check database slow queries
docker compose exec db psql -U app -c "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

**Solutions**:
1. Switch to faster LLM model
2. Optimize database queries
3. Increase backend workers
4. Reduce Langfuse sampling rate

### Memory Leaks

**Symptoms**: Memory usage continuously increases

**Diagnosis**:
```bash
# Monitor memory over time
docker stats --no-stream

# Check Python memory profiling
# Add memory_profiler to dev dependencies
```

**Solutions**:
1. Update dependencies (potential memory leaks)
2. Reduce concurrent workers
3. Enable periodic worker restarts
4. Investigate large object retention

### Rate Limiting Issues

**Symptoms**: Excessive rate limiting or no rate limiting

**Diagnosis**:
```bash
# Check Redis connectivity
docker compose exec backend redis-cli -h redis ping

# Check rate limit configuration
docker compose exec backend env | grep RATE_LIMIT
```

**Solutions**:
1. Adjust `RATE_LIMIT_PER_MINUTE` in `.env`
2. Verify Redis is accessible
3. Check for Redis memory issues
4. Consider per-user rate limit customization

## Appendix: Performance Test Results Template

```
# Performance Test Results
Date: YYYY-MM-DD
Version: X.Y.Z
Configuration: CONCURRENCY users, DURATION seconds

## Environment
- Deployment: Docker Compose / Kubernetes / Bare Metal
- Backend Workers: N
- Database: PostgreSQL version, RAM allocation
- Redis: Version, RAM allocation

## Results
- Total Requests: N
- Throughput: N req/s
- Rate Limit Hits: N (X%)

## Response Times
Endpoint | Count | Min | Max | Mean | P95 | P99
---------|-------|-----|-----|------|-----|----
agent/run| N     | Xs  | Xs  | Xs   | Xs  | Xs
get_runs | N     | Xms | Xms | Xms  | Xms | Xms
health   | N     | Xms | Xms | Xms  | Xms | Xms

## Resource Usage
Container | CPU Avg | CPU Max | Memory Avg | Memory Max
----------|---------|---------|------------|------------
backend   | X%      | X%      | XMB        | XMB
db        | X%      | X%      | XMB        | XMB
redis     | X%      | X%      | XMB        | XMB

## Issues
- List any errors or warnings
- Note any performance degradation
- Document any bottlenecks identified

## Recommendations
- Optimization suggestions
- Configuration changes needed
- Infrastructure scaling requirements
```

## Additional Resources

- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [FastAPI Performance](https://fastapi.tiangolo.com/deployment/concepts/)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Langfuse Documentation](https://langfuse.com/docs)
- [Redis Performance](https://redis.io/docs/management/optimization/)

## Conclusion

This performance guide provides comprehensive tools and methodologies for testing, monitoring, and optimizing the Unified FastAPI LLM Template. Regular performance testing and monitoring are essential for maintaining optimal system performance in production environments.

For questions or issues, please refer to the project documentation or open an issue on GitHub.
