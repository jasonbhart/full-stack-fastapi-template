# LLM Agent Architecture

This document describes the LLM agent architecture integrated into the Full Stack FastAPI template, including agent workflow design, distributed tracing, evaluation methodology, and configuration.

## Table of Contents

- [Overview](#overview)
- [Architecture Components](#architecture-components)
- [Agent Workflow Design](#agent-workflow-design)
- [Tracing Implementation](#tracing-implementation)
- [Evaluation Methodology](#evaluation-methodology)
- [Configuration Guide](#configuration-guide)
- [Development Workflow](#development-workflow)

## Overview

The template integrates LangGraph-based agent capabilities with Langfuse observability, providing a production-ready foundation for building AI-powered applications. The architecture preserves all baseline full-stack functionality while adding:

- **LangGraph Agent Orchestration**: State-based agent workflows with planner/executor pattern
- **Distributed Tracing**: Langfuse integration for observability and debugging
- **Evaluation Framework**: Automated evaluation of agent outputs using custom metrics
- **Rate Limiting**: Protection against abuse using Redis-backed rate limiting
- **Prometheus Metrics**: Operational monitoring and alerting capabilities

## Architecture Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │ Agent Chat   │  │ Agent History│  │ Langfuse Trace Links│  │
│  └──────────────┘  └──────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ JWT Auth + API Calls
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Python)                     │
│  ┌────────────────────────────────────────────────────────────┐│
│  │              API Layer (backend/app/api/routes/)            ││
│  │  • /api/v1/agent/run (POST) - Execute agent with input     ││
│  │  • /api/v1/agent/runs (GET) - Get paginated run history    ││
│  │  • /api/v1/agent/evaluations (POST) - Trigger evaluations  ││
│  │  Auth: get_current_active_user | Rate Limit: FastAPI-Limiter││
│  └────────────────────────────────────────────────────────────┘│
│                              │                                   │
│                              ▼                                   │
│  ┌────────────────────────────────────────────────────────────┐│
│  │            Agent Service (backend/app/agents/service.py)    ││
│  │  • Resolves user context from JWT                          ││
│  │  • Creates Langfuse traces/spans                           ││
│  │  • Invokes LangGraph workflow                              ││
│  │  • Persists run metadata to PostgreSQL (AgentRun table)    ││
│  └────────────────────────────────────────────────────────────┘│
│                              │                                   │
│                              ▼                                   │
│  ┌────────────────────────────────────────────────────────────┐│
│  │         LangGraph Workflow (backend/app/agents/graph.py)    ││
│  │                                                             ││
│  │  ┌─────────────┐      ┌──────────────┐      ┌──────────┐  ││
│  │  │   Planner   │ ───> │   Executor   │ ───> │   END    │  ││
│  │  │   Node      │      │   Node       │      │          │  ││
│  │  └─────────────┘      └──────────────┘      └──────────┘  ││
│  │       │                       │                            ││
│  │       │                       │                            ││
│  │       └───── Uses Tools ──────┘                            ││
│  │           (DB queries, HTTP)                               ││
│  │                                                             ││
│  │  • PostgreSQL checkpoint persistence for conversation      ││
│  │  • Langfuse callback handlers for trace capture           ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐│
│  │          Observability (backend/app/core/telemetry.py)      ││
│  │  • Langfuse client (lazy init, sampling controls)          ││
│  │  • Prometheus metrics (agent ops, latency, tokens)         ││
│  │  • Structured JSON logging with correlation IDs            ││
│  └────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      External Services                          │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────┐  ┌──────────┐ │
│  │ PostgreSQL  │  │  Langfuse   │  │  Redis   │  │OpenAI API│ │
│  │ (Persistence│  │ (Tracing UI)│  │(Rate Lim)│  │ (LLM)    │ │
│  │  + Memory)  │  └─────────────┘  └──────────┘  └──────────┘ │
│  └─────────────┘                                                │
│  ┌─────────────┐  ┌─────────────┐                              │
│  │ Prometheus  │  │   Grafana   │                              │
│  │  (Metrics)  │  │ (Dashboards)│                              │
│  └─────────────┘  └─────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

### Package Structure

```
backend/app/
├── agents/                    # LangGraph agent package
│   ├── __init__.py
│   ├── graph.py              # LangGraph workflow definitions
│   ├── tools.py              # LangChain tool registry (DB, HTTP)
│   ├── service.py            # Agent execution orchestration
│   └── schemas.py            # Pydantic request/response models
├── core/
│   ├── config.py             # Extended settings with LLM/Langfuse config
│   ├── telemetry.py          # Langfuse client + Prometheus metrics
│   ├── rate_limit.py         # FastAPI-Limiter setup
│   └── logging.py            # Structured logging with correlation IDs
├── models/
│   └── agent_models.py       # AgentRun, AgentEvaluation SQLModel tables
├── crud/
│   └── crud_agent.py         # CRUD operations for agent models
├── api/routes/
│   └── agent.py              # Agent API endpoints
└── evaluation/               # Evaluation framework
    ├── cli.py                # CLI for running evaluations
    ├── evaluator.py          # Core evaluation logic
    ├── schemas.py            # Evaluation data models
    └── metrics/              # Custom evaluation metrics
        ├── accuracy.py
        ├── coherence.py
        └── relevance.py
```

## Agent Workflow Design

### LangGraph State Graph

The agent uses a LangGraph state graph with a planner/executor pattern:

```python
class AgentState(TypedDict):
    """Agent state with conversation history."""
    messages: Annotated[list[BaseMessage], add_messages]
    plan: str | None
    user_id: str | None
```

**Workflow Steps:**

1. **Planner Node**:
   - Analyzes user request and conversation history
   - Creates execution plan identifying required tasks and tools
   - Uses LLM without tools for planning (prevents premature tool calls)
   - Outputs structured plan as string

2. **Executor Node**:
   - Receives plan and executes it
   - Has access to all registered tools (database queries, HTTP requests)
   - Uses LLM with tools to complete the plan
   - Returns final response to user

3. **Conditional Routing**:
   - After planner: always routes to executor
   - After executor: checks if more execution needed or ends

**Conversation Memory:**

- Uses PostgreSQL-backed checkpointing via `langgraph.checkpoint.postgres.PostgresSaver`
- Thread ID is generated as a random UUID per run unless explicitly provided by the caller
- To maintain conversation continuity across multiple interactions, pass the same `thread_id` when calling the agent service
- Messages automatically accumulated using `add_messages` reducer within a thread
- Enables multi-turn conversations with context awareness when using persistent thread IDs

### Tool Registry

Tools are created using factory functions in `backend/app/agents/tools.py`:

```python
def create_database_tools(session: Session) -> list[StructuredTool]:
    """Create database lookup tools with injected session.

    Returns three StructuredTool instances:
    """

    def lookup_user_by_email(email: str) -> str:
        """Look up a user by email address."""
        # Queries User table, returns JSON string with user data or error

    def lookup_item_by_id(item_id: str) -> str:
        """Look up an item by its UUID."""
        # Queries Item table, returns JSON string with item data or error

    def lookup_user_items(user_id: str, limit: int = 10) -> str:
        """Look up all items owned by a user."""
        # Queries Item table filtered by owner_id, returns JSON string

    return [
        StructuredTool.from_function(
            func=lookup_user_by_email,
            name="lookup_user_by_email",
            description="Find a user by their email address",
            args_schema=UserLookupInput,
        ),
        StructuredTool.from_function(
            func=lookup_item_by_id,
            name="lookup_item_by_id",
            description="Find an item by its UUID",
            args_schema=ItemLookupInput,
        ),
        StructuredTool.from_function(
            func=lookup_user_items,
            name="lookup_user_items",
            description="Get all items owned by a specific user",
            args_schema=UserItemsLookupInput,
        ),
    ]

# HTTP tools (stateless, decorated with @tool)
http_get: BaseTool    # Make HTTP GET requests with URL and optional headers
http_post: BaseTool   # Make HTTP POST requests with URL, data, and headers

# Combined registry
def get_all_tools(session: Session | None = None) -> list[BaseTool]:
    """Get all available tools for agent use."""
    tools = []
    if session is not None:
        tools.extend(create_database_tools(session))
    tools.extend([http_get, http_post])
    return tools
```

**Tool Design Principles:**
- Stateless: No shared state between tool invocations
- Dependency Injection: Database sessions injected via factory pattern
- Error Handling: All tools return JSON strings with error messages on failure
- Type Safety: Pydantic schemas for inputs (e.g., `UserLookupInput`, `ItemLookupInput`)

### Agent Service Orchestration

The `AgentService` class orchestrates execution:

```python
async def run_agent(
    self,
    user: User,
    message: str,
    thread_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Execute agent workflow with tracing.

    1. Create Langfuse trace with user_id and metadata
    2. Generate thread_id if not provided (for conversation continuity)
    3. Build LangGraph config with callbacks
    4. Invoke graph with user message
    5. Persist run metadata to AgentRun table (when implemented)
    6. Return response with trace_id, thread_id, run_id, and status

    Returns:
        {
            "response": str,          # Agent's response message
            "thread_id": str,         # Thread ID (for conversation continuity)
            "trace_id": str | None,   # Langfuse trace ID
            "run_id": str,            # Database run ID
            "latency_ms": int,        # Execution time
            "status": str,            # "success" or "error"
            "plan": str | None,       # Planner's execution plan (from graph state)
        }
    """
```

## Tracing Implementation

### Langfuse Integration

**Initialization (Lazy Loading):**

```python
# In backend/app/core/telemetry.py
def get_langfuse_client() -> Langfuse | None:
    """Get or initialize Langfuse client."""
    global _langfuse_client

    if not settings.LANGFUSE_ENABLED:
        return None

    if _langfuse_client is None:
        _langfuse_client = Langfuse(
            secret_key=settings.LANGFUSE_SECRET_KEY,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            host=settings.LANGFUSE_HOST,
        )

    return _langfuse_client
```

**Trace Creation:**

```python
# In agent service
handler = CallbackHandler(
    secret_key=settings.LANGFUSE_SECRET_KEY,
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    host=settings.LANGFUSE_HOST,
    sample_rate=settings.LANGFUSE_SAMPLE_RATE,
)

# Create trace with metadata
handler.trace = handler.langfuse.trace(
    name="agent_run",
    user_id=user.id,
    metadata={
        "user_id": user.id,
        "app_env": settings.APP_ENV.value,
        **custom_metadata,
    },
)
```

**Context Propagation:**

- Context variables (`ContextVar`) track current trace/span across async operations
- Langfuse callback handler automatically propagates to LangChain/LangGraph calls
- Correlation IDs in structured logs linked to trace IDs

**Trace Data:**

Each trace captures:
- Input prompts and messages
- LLM responses and tool calls
- Token usage (prompt + completion)
- Latency for each operation
- User context and environment
- Custom metadata from application

**Sampling Controls:**

```python
LANGFUSE_SAMPLE_RATE: float = 1.0  # 0.0 to 1.0

# In handler creation:
sample_rate=settings.LANGFUSE_SAMPLE_RATE
```

### Prometheus Metrics

Custom metrics following Prometheus naming conventions:

```python
# Counters
agent_invocations_total              # Total agent invocations
agent_invocations_by_status_total    # By status: completed/failed/timeout
agent_tokens_total                   # Total tokens used

# Histograms
agent_execution_duration_seconds     # Latency distribution
agent_prompt_tokens                  # Prompt token distribution
agent_completion_tokens              # Completion token distribution

# Gauges
agent_active_executions              # Currently running agents

# Info
app_info                             # App metadata (version, env)
```

**Metrics Endpoint:**

```
GET /metrics
```

Returns Prometheus-formatted metrics for scraping.

**Grafana Dashboards:**

Pre-configured dashboards in `deployment/grafana/dashboards/`:
- Agent performance overview
- Token usage and costs
- Error rates and latency percentiles
- Active executions over time

## Evaluation Methodology

### Architecture

The evaluation system consumes Langfuse trace data and applies custom metrics using an LLM-as-judge pattern:

```
┌─────────────────┐
│  Langfuse API   │
│  (Trace Data)   │
│  Last 24 hours  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  Evaluation CLI             │
│  (backend/app/evaluation/)  │
│                             │
│  1. Fetch unscored traces   │
│  2. Apply metrics from      │
│     markdown prompts        │
│  3. Upload scores to        │
│     Langfuse               │
│  4. Generate JSON report    │
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Prompt-Based Metrics       │
│  • Conciseness              │
│  • Hallucination            │
│  • Helpfulness              │
│  • Relevancy                │
│  • Toxicity                 │
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Langfuse Scores            │
│  (Associated with traces)   │
└─────────────────────────────┘
```

### Custom Metrics

Metrics are defined as markdown prompt files in `backend/app/evaluation/metrics/prompts/`:

**Available Metrics:**
- `conciseness.md` - Evaluates response brevity and clarity
- `hallucination.md` - Detects factual inaccuracies or fabrications
- `helpfulness.md` - Measures how well the response addresses the user's need
- `relevancy.md` - Checks response relevance to the user query
- `toxicity.md` - Identifies harmful, offensive, or inappropriate content

**How Metrics Work:**

Each metric is a markdown file containing an LLM prompt that evaluates the trace input/output:

```markdown
# Metric Name

Evaluate the following conversation for [criteria].

Input: {input}
Output: {output}

Score from 0.0 to 1.0 where:
- 1.0 = [excellent condition]
- 0.0 = [poor condition]

Return only the numeric score.
```

The evaluator loads these prompts dynamically from the `prompts/` directory:

```python
# In backend/app/evaluation/metrics/__init__.py
metrics: list[dict[str, str]] = []

for file in os.listdir(PROMPTS_DIR):
    if file.endswith(".md"):
        with open(os.path.join(PROMPTS_DIR, file)) as f:
            metrics.append({
                "name": file.replace(".md", ""),
                "prompt": f.read()
            })
```

### Running Evaluations

**CLI Usage:**

The CLI evaluates all unscored traces from the last 24 hours:

```bash
# Run evaluations (generates report by default)
uv run python -m app.evaluation.cli

# Run without generating report file
uv run python -m app.evaluation.cli --no-report
```

**Note:** The evaluation window is fixed to 24 hours and cannot be customized via CLI arguments.

**Programmatic Usage:**

```python
from app.evaluation import Evaluator

# Create evaluator (no constructor arguments needed)
evaluator = Evaluator()

# Run evaluation on last 24 hours of traces
report = await evaluator.run(generate_report_file=True)

# Report structure:
# {
#     "timestamp": "2025-01-15T10:30:00",
#     "model": "gpt-4o-mini",
#     "total_traces": 50,
#     "successful_traces": 48,
#     "failed_traces": 2,
#     "duration_seconds": 125.5,
#     "metrics_summary": {
#         "conciseness": {"success_count": 48, "failure_count": 2, "avg_score": 0.85},
#         "helpfulness": {"success_count": 47, "failure_count": 3, "avg_score": 0.92},
#         ...
#     },
#     "report_path": "reports/evaluation_20250115_103000.json"
# }
```

### Evaluation Data Model

Scores are uploaded to Langfuse and associated with traces. For local persistence, the `AgentEvaluation` model can be used:

```python
class AgentEvaluation(SQLModel, table=True):
    id: uuid.UUID
    run_id: uuid.UUID                    # FK to AgentRun
    metric_name: str                     # e.g., "helpfulness"
    score: float                         # 0.0 to 1.0
    eval_metadata: dict[str, Any] | None # Additional evaluation context
    created_at: datetime
```

**Note:** The field is `eval_metadata`, not `metadata`.

## Configuration Guide

### Environment-Specific Configuration

The application uses `APP_ENV` to load environment-specific settings:

```bash
# .env (base configuration)
APP_ENV=local

# Settings resolution chain:
# 1. Environment variables (highest priority)
# 2. .env.{APP_ENV} file (e.g., .env.local, .env.production)
# 3. .env file (lowest priority)
```

**Environment Values:**

- `local`: Local development (default)
- `staging`: Staging environment
- `production`: Production environment
- `test`: Testing environment

### LLM Configuration

```bash
# Model Selection
LLM_MODEL_NAME=gpt-4
LLM_MODEL_PROVIDER=openai  # openai | anthropic | azure
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048

# Provider API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Azure OpenAI (if using azure provider)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### LangChain/LangSmith Configuration

```bash
# Optional: LangSmith tracing (alternative to Langfuse)
LANGCHAIN_API_KEY=ls_...
LANGCHAIN_TRACING_V2=false
LANGCHAIN_PROJECT=my-project
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

### Langfuse Configuration

```bash
# Langfuse Observability
LANGFUSE_ENABLED=true
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_SAMPLE_RATE=1.0  # 0.0 to 1.0 (1.0 = 100% traces captured)
```

**Sampling Strategy:**

- `1.0`: Capture all traces (development)
- `0.1`: Capture 10% of traces (production, high volume)
- `0.0`: Disable tracing

### Rate Limiting Configuration

```bash
# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60

# Redis Backend
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=          # Optional
REDIS_DB=0
```

**Rate Limit Application:**

```python
# In backend/app/api/routes/agent.py
from app.core.rate_limit import limiter

@router.post("/run")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def run_agent(
    message: str,
    current_user: User = Depends(get_current_active_user),
):
    # Protected endpoint
    pass
```

### Evaluation Configuration

```bash
# Evaluation Settings
EVALUATION_API_KEY=sk-...         # API key for evaluation LLM
EVALUATION_BASE_URL=https://api.openai.com/v1
EVALUATION_LLM=gpt-4o-mini        # Model for evaluations (cost-effective)
EVALUATION_SLEEP_TIME=1           # Seconds between evaluations (rate limit)
```

### Example Configurations

**.env.local (Development):**

```bash
APP_ENV=local

# LLM (use cheaper models for dev)
LLM_MODEL_NAME=gpt-3.5-turbo
OPENAI_API_KEY=sk-...

# Langfuse (capture all traces)
LANGFUSE_ENABLED=true
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SAMPLE_RATE=1.0

# Rate Limiting (permissive)
RATE_LIMIT_ENABLED=false
```

**.env.production (Production):**

```bash
APP_ENV=production

# LLM (production model)
LLM_MODEL_NAME=gpt-4
OPENAI_API_KEY=sk-...

# Langfuse (sample traces)
LANGFUSE_ENABLED=true
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SAMPLE_RATE=0.1  # 10% sampling

# Rate Limiting (strict)
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60

# Redis (production instance)
REDIS_HOST=redis.production.internal
REDIS_PASSWORD=...
```

## Development Workflow

### Local Development

**1. Start Services:**

```bash
# Start all services with live reload
docker compose watch

# Or start backend only for frontend development
docker compose up -d --wait backend redis postgres langfuse
```

**2. Run Backend Locally:**

```bash
cd backend
source .venv/bin/activate
fastapi dev app/main.py
```

**3. Frontend Development:**

```bash
cd frontend
npm run dev
```

**4. Access Services:**

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Langfuse UI: http://localhost:3001
- Grafana: http://localhost:3002
- Prometheus: http://localhost:9090

### Testing Agent Workflows

**1. Via API:**

```bash
# Authenticate
TOKEN=$(curl -X POST http://localhost:8000/api/v1/login/access-token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethis" | jq -r .access_token)

# Run agent
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "What users are in the system?"}'

# Get run history
curl http://localhost:8000/api/v1/agent/runs \
  -H "Authorization: Bearer $TOKEN"
```

**2. Via Frontend:**

- Login to dashboard
- Navigate to Agent Chat (if feature flag enabled)
- Enter prompt and view streaming response
- Click trace link to view in Langfuse

**3. View Traces:**

- Open Langfuse UI: http://localhost:3001
- Browse traces by user, date, or trace ID
- Inspect LLM calls, tool usage, and latency
- Debug errors and optimize prompts

### Running Evaluations

```bash
# Activate backend environment
cd backend
source .venv/bin/activate

# Run evaluations on last 24 hours of traces (generates report by default)
uv run python -m app.evaluation.cli

# Run without generating report file
uv run python -m app.evaluation.cli --no-report

# View generated report
cat backend/reports/evaluation_*.json | jq .

# Scores are uploaded to Langfuse and can be viewed in the Langfuse UI
```

### Monitoring and Observability

**Prometheus Metrics:**

```bash
# View metrics
curl http://localhost:8000/metrics

# Example queries in Prometheus UI:
# - agent_invocations_total{status="completed"}
# - rate(agent_execution_duration_seconds_sum[5m])
# - agent_active_executions
```

**Grafana Dashboards:**

1. Open Grafana: http://localhost:3002
2. Navigate to Dashboards
3. Select "Agent Performance Overview"
4. View metrics:
   - Request rate and latency
   - Token usage and costs
   - Error rates
   - Active executions

**Structured Logs:**

```bash
# View agent logs (JSON format in production)
docker compose logs -f backend | grep agent_run

# Correlation ID filtering
docker compose logs backend | jq 'select(.correlation_id == "abc-123")'
```

### Debugging

**Common Issues:**

1. **Langfuse traces not appearing:**
   - Check `LANGFUSE_ENABLED=true`
   - Verify API keys are correct
   - Check `LANGFUSE_SAMPLE_RATE` (must be > 0)
   - Review backend logs for Langfuse errors

2. **Rate limiting not working:**
   - Ensure Redis is running: `docker compose ps redis`
   - Check `RATE_LIMIT_ENABLED=true`
   - Verify Redis connection: `redis-cli -h localhost ping`

3. **Agent execution errors:**
   - Check OpenAI API key is valid
   - Review tool implementations for errors
   - Inspect Langfuse trace for exact error
   - Check PostgreSQL checkpointer connection

4. **Conversation memory not persisting:**
   - Verify PostgreSQL checkpointer setup in graph.py
   - Check thread_id matches user_id pattern
   - Review database migrations for checkpoint tables

## Best Practices

### Security

1. **API Keys**: Never commit API keys to version control
2. **Rate Limiting**: Always enable in production (`RATE_LIMIT_ENABLED=true`)
3. **Authentication**: All agent endpoints require JWT authentication
4. **CORS**: Configure `BACKEND_CORS_ORIGINS` appropriately for production
5. **Sampling**: Use `LANGFUSE_SAMPLE_RATE < 1.0` in high-volume production

### Performance

1. **Model Selection**: Use faster models (gpt-3.5-turbo) for development
2. **Sampling**: Reduce trace sampling in production to minimize overhead
3. **Tool Design**: Keep tools lightweight and stateless
4. **Checkpointing**: Use PostgreSQL checkpointer for production (not SQLite)
5. **Streaming**: Implement streaming responses for better UX (future enhancement)

### Observability

1. **Structured Logging**: Always use JSON logs in production
2. **Correlation IDs**: Include in all logs for trace linking
3. **Metrics**: Monitor token usage to control costs
4. **Alerts**: Set up Prometheus alerts for error rates and latency
5. **Evaluation**: Run regular evaluations to track quality over time

### Development

1. **Environment Isolation**: Use `.env.local` for development settings
2. **Testing**: Mock LLM responses in unit tests for reliability
3. **Feature Flags**: Use `VITE_ENABLE_AGENT` to toggle frontend features
4. **Documentation**: Update this doc when adding new metrics or features
5. **Migrations**: Always create Alembic migrations for schema changes

## References

- [LangChain Documentation](https://python.langchain.com/docs/get_started/introduction)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Langfuse Documentation](https://langfuse.com/docs)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
