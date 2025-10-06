# Full Stack FastAPI Template

<a href="https://github.com/fastapi/full-stack-fastapi-template/actions?query=workflow%3ATest" target="_blank"><img src="https://github.com/fastapi/full-stack-fastapi-template/workflows/Test/badge.svg" alt="Test"></a>
<a href="https://coverage-badge.samuelcolvin.workers.dev/redirect/fastapi/full-stack-fastapi-template" target="_blank"><img src="https://coverage-badge.samuelcolvin.workers.dev/fastapi/full-stack-fastapi-template.svg" alt="Coverage"></a>

## Technology Stack and Features

- ⚡ [**FastAPI**](https://fastapi.tiangolo.com) for the Python backend API.
    - 🧰 [SQLModel](https://sqlmodel.tiangolo.com) for the Python SQL database interactions (ORM).
    - 🔍 [Pydantic](https://docs.pydantic.dev), used by FastAPI, for the data validation and settings management.
    - 💾 [PostgreSQL](https://www.postgresql.org) as the SQL database.
- 🚀 [React](https://react.dev) for the frontend.
    - 💃 Using TypeScript, hooks, Vite, and other parts of a modern frontend stack.
    - 🎨 [Chakra UI](https://chakra-ui.com) for the frontend components.
    - 🤖 An automatically generated frontend client.
    - 🧪 [Playwright](https://playwright.dev) for End-to-End testing.
    - 🦇 Dark mode support.
- 🐋 [Docker Compose](https://www.docker.com) for development and production.
- 🔒 Secure password hashing by default.
- 🔑 JWT (JSON Web Token) authentication.
- 📫 Email based password recovery.
- ✅ Tests with [Pytest](https://pytest.org).
- 📞 [Traefik](https://traefik.io) as a reverse proxy / load balancer.
- 🚢 Deployment instructions using Docker Compose, including how to set up a frontend Traefik proxy to handle automatic HTTPS certificates.
- 🏭 CI (continuous integration) and CD (continuous deployment) based on GitHub Actions.
- 🤖 **[NEW]** [**LangGraph**](https://langchain-ai.github.io/langgraph/) powered AI agents with LLM orchestration.
    - 🧠 State-based agent workflows with planner/executor pattern.
    - 🔍 [Langfuse](https://langfuse.com) integration for LLM observability and tracing.
    - 📊 Automated evaluation framework with LLM-as-judge pattern.
    - 🛡️ Rate limiting with Redis to protect agent endpoints.
    - 📈 Prometheus metrics and Grafana dashboards for monitoring.

## 🚀 LLM Features Quick Start

This template includes production-ready AI agent capabilities powered by LangGraph and LangChain. Follow these steps to get started with LLM features.

### Prerequisites

- An OpenAI API key (or Anthropic/Azure OpenAI)
- Optional: Langfuse account for observability ([free cloud](https://cloud.langfuse.com) or [self-hosted](https://langfuse.com/docs/deployment/self-host))

### 1. Configure API Keys

Copy the `.env.local.example` file to `.env.local` and add your API keys:

```bash
# Copy the local environment template
cp .env.local.example .env.local

# Edit the file and add your keys
nano .env.local
```

**Minimum required configuration:**

```bash
# Your OpenAI API key
OPENAI_API_KEY=sk-...

# Enable agent features in frontend (optional)
VITE_ENABLE_AGENT=true
```

**Recommended for development:**

```bash
# Use faster, cheaper models for development
LLM_MODEL_NAME=gpt-3.5-turbo

# Enable Langfuse tracing (optional but recommended)
LANGFUSE_ENABLED=true
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SAMPLE_RATE=1.0

# Evaluation API key (can be same as OPENAI_API_KEY)
EVALUATION_API_KEY=sk-...
```

**For production:**

```bash
# Use production-grade models
LLM_MODEL_NAME=gpt-4

# Sample traces to reduce overhead (10% sampling)
LANGFUSE_SAMPLE_RATE=0.1

# Enable rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
```

See [`.env.example`](.env.example) for all available configuration options.

### 2. Start the Stack

Start all services including Redis, Langfuse, Prometheus, and Grafana:

```bash
# Start services with live reload
docker compose watch

# Or for production
docker compose up -d
```

**Available services:**

- **Backend API:** http://localhost:8000
- **Frontend:** http://localhost:5173
- **API Docs:** http://localhost:8000/docs
- **Langfuse UI:** http://localhost:3001
- **Grafana:** http://localhost:3002
- **Prometheus:** http://localhost:9090

### 3. Test the Agent

**Via Frontend (if `VITE_ENABLE_AGENT=true`):**

1. Login to the dashboard: http://localhost:5173
2. Navigate to the Agent Chat
3. Enter a prompt: "What users are in the system?"
4. View the agent's response and click the trace link to see execution details in Langfuse

**Via API:**

```bash
# Get authentication token
TOKEN=$(curl -X POST http://localhost:8000/api/v1/login/access-token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethisnowplease" \
  | jq -r .access_token)

# Run the agent
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What users are in the system?"
  }'

# Get run history
curl http://localhost:8000/api/v1/agent/runs \
  -H "Authorization: Bearer $TOKEN"
```

### 4. View Traces and Metrics

**Langfuse (Observability):**

1. Open http://localhost:3001
2. Browse traces to see:
   - LLM calls and responses
   - Tool usage (database queries, HTTP requests)
   - Token counts and costs
   - Latency breakdown
   - Error details

**Grafana (Metrics):**

1. Open http://localhost:3002 (login: admin/admin)
2. Navigate to Dashboards → Agent Performance
3. View metrics:
   - Request rates and success rates
   - Latency percentiles (p50, p95, p99)
   - Token usage over time
   - Active agent executions

**Prometheus (Raw Metrics):**

- View raw metrics: http://localhost:8000/metrics
- Query metrics: http://localhost:9090

### 5. Run Evaluations

Evaluate agent outputs using the built-in evaluation framework:

```bash
# Activate backend environment
cd backend
source .venv/bin/activate

# Run evaluations on last 24 hours of traces
uv run python -m app.evaluation.cli

# View the generated report
cat reports/evaluation_*.json | jq .
```

The evaluation system uses LLM-as-judge to score agent responses on:
- **Conciseness:** Response brevity and clarity
- **Hallucination:** Factual accuracy
- **Helpfulness:** How well it addresses the user's need
- **Relevancy:** Relevance to the query
- **Toxicity:** Harmful or inappropriate content

Scores are uploaded to Langfuse and included in trace metadata.

## 💡 Example Use Cases

### Database Queries

```bash
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How many items does the admin user have?"
  }'
```

The agent will:
1. Use the `lookup_user_by_email` tool to find the admin user
2. Use the `lookup_user_items` tool to count their items
3. Return a natural language response

### Multi-turn Conversations

```bash
# First message - agent generates a thread_id
RESPONSE=$(curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Who is the admin user?"}')

# Extract thread_id for conversation continuity
THREAD_ID=$(echo $RESPONSE | jq -r .thread_id)

# Follow-up message in same conversation
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"What items do they have?\",
    \"thread_id\": \"$THREAD_ID\"
  }"
```

The agent maintains conversation context using PostgreSQL-backed memory.

### HTTP Requests

```bash
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Fetch the latest GitHub issues from fastapi/fastapi"
  }'
```

The agent can use the `http_get` tool to fetch external data.

## 🔧 Troubleshooting

### Agent Not Responding

**Problem:** Agent returns errors or timeouts.

**Solutions:**

1. **Check API key:**
   ```bash
   # Test OpenAI API key
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

2. **Check backend logs:**
   ```bash
   docker compose logs backend | grep -i error
   ```

3. **Verify model name:**
   - Ensure `LLM_MODEL_NAME` is valid (e.g., `gpt-4`, `gpt-3.5-turbo`)
   - Check available models in OpenAI dashboard

4. **Check rate limits:**
   - Review OpenAI usage: https://platform.openai.com/usage
   - Temporarily disable rate limiting: `RATE_LIMIT_ENABLED=false`

### Langfuse Traces Not Appearing

**Problem:** No traces visible in Langfuse UI.

**Solutions:**

1. **Verify configuration:**
   ```bash
   # Check environment variables
   docker compose exec backend printenv | grep LANGFUSE
   ```

2. **Check sampling rate:**
   - Ensure `LANGFUSE_SAMPLE_RATE > 0` (1.0 = 100%)
   - Set `LANGFUSE_SAMPLE_RATE=1.0` for development

3. **Verify API keys:**
   - Check keys are correct in `.env.local`
   - Test Langfuse connection: http://localhost:3001

4. **Check backend logs:**
   ```bash
   docker compose logs backend | grep langfuse
   ```

### Redis Connection Errors

**Problem:** Rate limiting fails with Redis errors.

**Solutions:**

1. **Check Redis is running:**
   ```bash
   docker compose ps redis
   ```

2. **Test Redis connection:**
   ```bash
   docker compose exec redis redis-cli ping
   # Should return: PONG
   ```

3. **Restart Redis:**
   ```bash
   docker compose restart redis
   ```

4. **Temporarily disable rate limiting:**
   ```bash
   # In .env.local
   RATE_LIMIT_ENABLED=false
   ```

### Database Migration Issues

**Problem:** Agent tables not found.

**Solutions:**

1. **Run migrations:**
   ```bash
   docker compose exec backend alembic upgrade head
   ```

2. **Check migration status:**
   ```bash
   docker compose exec backend alembic current
   ```

3. **Reset database (development only):**
   ```bash
   docker compose down -v
   docker compose up -d
   ```

### High Costs / Token Usage

**Problem:** Unexpectedly high OpenAI bills.

**Solutions:**

1. **Use cheaper models for development:**
   ```bash
   LLM_MODEL_NAME=gpt-3.5-turbo
   ```

2. **Monitor token usage:**
   - View in Langfuse: http://localhost:3001
   - Check Grafana metrics: http://localhost:3002
   - Query Prometheus: `agent_tokens_total`

3. **Enable sampling in production:**
   ```bash
   LANGFUSE_SAMPLE_RATE=0.1  # Only trace 10%
   ```

4. **Reduce max tokens:**
   ```bash
   LLM_MAX_TOKENS=1024  # Lower limit
   ```

### Evaluation Errors

**Problem:** Evaluation CLI fails or returns no results.

**Solutions:**

1. **Check evaluation API key:**
   ```bash
   # Should be set (can be same as OPENAI_API_KEY)
   echo $EVALUATION_API_KEY
   ```

2. **Verify traces exist:**
   - Check Langfuse UI for traces from last 24 hours
   - The CLI only evaluates unscored traces

3. **Check evaluation logs:**
   ```bash
   cd backend
   source .venv/bin/activate
   uv run python -m app.evaluation.cli 2>&1 | tee evaluation.log
   ```

4. **Increase sleep time if rate limited:**
   ```bash
   EVALUATION_SLEEP_TIME=2  # Wait 2 seconds between evaluations
   ```

### Performance Issues

**Problem:** Slow agent responses or need to measure system performance.

**Solutions:**

1. **Run Performance Tests:**
   ```bash
   # Quick performance test
   ./scripts/run_performance_tests.sh

   # Custom test duration and concurrency
   DURATION=60 CONCURRENCY=25 ./scripts/run_performance_tests.sh
   ```

   See [Performance Testing Guide](docs/PERFORMANCE_TESTING_GUIDE.md) for detailed instructions.

2. **Use faster models:**
   ```bash
   LLM_MODEL_NAME=gpt-3.5-turbo  # Faster than gpt-4
   ```

3. **Optimize tool usage:**
   - Reduce number of tools available
   - Simplify tool implementations

4. **Check infrastructure:**
   - Ensure adequate CPU/memory for Docker containers
   - Monitor with Grafana: http://localhost:3002
   - Run resource monitoring: `python3 scripts/monitor_resources.py`

5. **Reduce trace sampling:**
   ```bash
   LANGFUSE_SAMPLE_RATE=0.1  # Reduce overhead
   ```

6. **Review performance documentation:**
   - See [docs/PERFORMANCE.md](docs/PERFORMANCE.md) for comprehensive performance optimization guide

## 📚 Additional Resources

- **Architecture Documentation:** [docs/architecture/llm-agents.md](docs/architecture/llm-agents.md)
- **Performance Guide:** [docs/PERFORMANCE.md](docs/PERFORMANCE.md)
- **Performance Testing:** [docs/PERFORMANCE_TESTING_GUIDE.md](docs/PERFORMANCE_TESTING_GUIDE.md)
- **LangGraph Documentation:** https://langchain-ai.github.io/langgraph/
- **Langfuse Documentation:** https://langfuse.com/docs
- **Backend Development:** [backend/README.md](./backend/README.md)
- **Frontend Development:** [frontend/README.md](./frontend/README.md)

---

### Dashboard Login

[![API docs](img/login.png)](https://github.com/fastapi/full-stack-fastapi-template)

### Dashboard - Admin

[![API docs](img/dashboard.png)](https://github.com/fastapi/full-stack-fastapi-template)

### Dashboard - Create User

[![API docs](img/dashboard-create.png)](https://github.com/fastapi/full-stack-fastapi-template)

### Dashboard - Items

[![API docs](img/dashboard-items.png)](https://github.com/fastapi/full-stack-fastapi-template)

### Dashboard - User Settings

[![API docs](img/dashboard-user-settings.png)](https://github.com/fastapi/full-stack-fastapi-template)

### Dashboard - Dark Mode

[![API docs](img/dashboard-dark.png)](https://github.com/fastapi/full-stack-fastapi-template)

### Interactive API Documentation

[![API docs](img/docs.png)](https://github.com/fastapi/full-stack-fastapi-template)

## How To Use It

You can **just fork or clone** this repository and use it as is.

✨ It just works. ✨

### How to Use a Private Repository

If you want to have a private repository, GitHub won't allow you to simply fork it as it doesn't allow changing the visibility of forks.

But you can do the following:

- Create a new GitHub repo, for example `my-full-stack`.
- Clone this repository manually, set the name with the name of the project you want to use, for example `my-full-stack`:

```bash
git clone git@github.com:fastapi/full-stack-fastapi-template.git my-full-stack
```

- Enter into the new directory:

```bash
cd my-full-stack
```

- Set the new origin to your new repository, copy it from the GitHub interface, for example:

```bash
git remote set-url origin git@github.com:octocat/my-full-stack.git
```

- Add this repo as another "remote" to allow you to get updates later:

```bash
git remote add upstream git@github.com:fastapi/full-stack-fastapi-template.git
```

- Push the code to your new repository:

```bash
git push -u origin master
```

### Update From the Original Template

After cloning the repository, and after doing changes, you might want to get the latest changes from this original template.

- Make sure you added the original repository as a remote, you can check it with:

```bash
git remote -v

origin    git@github.com:octocat/my-full-stack.git (fetch)
origin    git@github.com:octocat/my-full-stack.git (push)
upstream    git@github.com:fastapi/full-stack-fastapi-template.git (fetch)
upstream    git@github.com:fastapi/full-stack-fastapi-template.git (push)
```

- Pull the latest changes without merging:

```bash
git pull --no-commit upstream master
```

This will download the latest changes from this template without committing them, that way you can check everything is right before committing.

- If there are conflicts, solve them in your editor.

- Once you are done, commit the changes:

```bash
git merge --continue
```

### Configure

You can then update configs in the `.env` files to customize your configurations.

Before deploying it, make sure you change at least the values for:

- `SECRET_KEY`
- `FIRST_SUPERUSER_PASSWORD`
- `POSTGRES_PASSWORD`

You can (and should) pass these as environment variables from secrets.

Read the [deployment.md](./deployment.md) docs for more details.

### Generate Secret Keys

Some environment variables in the `.env` file have a default value of `changethis`.

You have to change them with a secret key, to generate secret keys you can run the following command:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the content and use that as password / secret key. And run that again to generate another secure key.

## How To Use It - Alternative With Copier

This repository also supports generating a new project using [Copier](https://copier.readthedocs.io).

It will copy all the files, ask you configuration questions, and update the `.env` files with your answers.

### Install Copier

You can install Copier with:

```bash
pip install copier
```

Or better, if you have [`pipx`](https://pipx.pypa.io/), you can run it with:

```bash
pipx install copier
```

**Note**: If you have `pipx`, installing copier is optional, you could run it directly.

### Generate a Project With Copier

Decide a name for your new project's directory, you will use it below. For example, `my-awesome-project`.

Go to the directory that will be the parent of your project, and run the command with your project's name:

```bash
copier copy https://github.com/fastapi/full-stack-fastapi-template my-awesome-project --trust
```

If you have `pipx` and you didn't install `copier`, you can run it directly:

```bash
pipx run copier copy https://github.com/fastapi/full-stack-fastapi-template my-awesome-project --trust
```

**Note** the `--trust` option is necessary to be able to execute a [post-creation script](https://github.com/fastapi/full-stack-fastapi-template/blob/master/.copier/update_dotenv.py) that updates your `.env` files.

### Input Variables

Copier will ask you for some data, you might want to have at hand before generating the project.

But don't worry, you can just update any of that in the `.env` files afterwards.

The input variables, with their default values (some auto generated) are:

- `project_name`: (default: `"FastAPI Project"`) The name of the project, shown to API users (in .env).
- `stack_name`: (default: `"fastapi-project"`) The name of the stack used for Docker Compose labels and project name (no spaces, no periods) (in .env).
- `secret_key`: (default: `"changethis"`) The secret key for the project, used for security, stored in .env, you can generate one with the method above.
- `first_superuser`: (default: `"admin@example.com"`) The email of the first superuser (in .env).
- `first_superuser_password`: (default: `"changethis"`) The password of the first superuser (in .env).
- `smtp_host`: (default: "") The SMTP server host to send emails, you can set it later in .env.
- `smtp_user`: (default: "") The SMTP server user to send emails, you can set it later in .env.
- `smtp_password`: (default: "") The SMTP server password to send emails, you can set it later in .env.
- `emails_from_email`: (default: `"info@example.com"`) The email account to send emails from, you can set it later in .env.
- `postgres_password`: (default: `"changethis"`) The password for the PostgreSQL database, stored in .env, you can generate one with the method above.
- `sentry_dsn`: (default: "") The DSN for Sentry, if you are using it, you can set it later in .env.

## Backend Development

Backend docs: [backend/README.md](./backend/README.md).

## Frontend Development

Frontend docs: [frontend/README.md](./frontend/README.md).

## Deployment

Deployment docs: [deployment.md](./deployment.md).

## Development

General development docs: [development.md](./development.md).

This includes using Docker Compose, custom local domains, `.env` configurations, etc.

## Release Notes

Check the file [release-notes.md](./release-notes.md).

## License

The Full Stack FastAPI Template is licensed under the terms of the MIT license.
