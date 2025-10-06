# Full Stack FastAPI Template - Makefile
#
# This Makefile provides convenient targets for common development tasks.
# All targets are idempotent and can be run multiple times safely.

.PHONY: help
help: ## Show this help message
	@echo "Full Stack FastAPI Template - Available Make Targets"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

# ============================================================================
# Docker Compose Management
# ============================================================================

.PHONY: up
up: ## Start all services with docker-compose
	docker compose up -d

.PHONY: down
down: ## Stop all services
	docker compose down

.PHONY: restart
restart: down up ## Restart all services

.PHONY: logs
logs: ## View logs from all services (use Ctrl+C to exit)
	docker compose logs -f

.PHONY: logs-backend
logs-backend: ## View backend logs only
	docker compose logs -f backend

.PHONY: logs-frontend
logs-frontend: ## View frontend logs only
	docker compose logs -f frontend

.PHONY: ps
ps: ## Show running services
	docker compose ps

# ============================================================================
# Development
# ============================================================================

.PHONY: watch
watch: ## Start services with live reload (watch mode)
	docker compose watch

.PHONY: build
build: ## Build all Docker images
	docker compose build

.PHONY: clean
clean: ## Remove all containers, volumes, and images
	docker compose down -v --remove-orphans
	docker compose rm -f

# ============================================================================
# Backend Development
# ============================================================================

.PHONY: backend-shell
backend-shell: ## Open a shell in the backend container
	docker compose exec backend bash

.PHONY: backend-logs
backend-logs: logs-backend ## Alias for logs-backend

.PHONY: migrate
migrate: ## Run database migrations
	docker compose exec backend alembic upgrade head

.PHONY: migration
migration: ## Create a new database migration (use MESSAGE="description")
	@if [ -z "$(MESSAGE)" ]; then \
		echo "Error: MESSAGE is required. Usage: make migration MESSAGE=\"your description\""; \
		exit 1; \
	fi
	docker compose exec backend alembic revision --autogenerate -m "$(MESSAGE)"

.PHONY: db-reset
db-reset: ## Reset database (WARNING: destroys all data)
	@echo "WARNING: This will destroy all database data. Press Ctrl+C to cancel..."
	@sleep 5
	docker compose down -v
	docker compose up -d db
	@echo "Waiting for database to be ready..."
	@sleep 5
	docker compose up -d backend
	@echo "Running migrations..."
	@sleep 5
	$(MAKE) migrate

# ============================================================================
# Frontend Development
# ============================================================================

.PHONY: frontend-shell
frontend-shell: ## Open a shell in the frontend container
	docker compose exec frontend sh

.PHONY: frontend-logs
frontend-logs: logs-frontend ## Alias for logs-frontend

.PHONY: generate-client
generate-client: ## Generate frontend API client from OpenAPI spec
	./scripts/generate-client.sh

# ============================================================================
# Testing
# ============================================================================

.PHONY: test
test: ## Run all backend tests
	docker compose exec backend bash scripts/test.sh

.PHONY: test-coverage
test-coverage: ## Run backend tests with coverage report
	docker compose exec backend bash scripts/test.sh
	@echo "Coverage report available at backend/htmlcov/index.html"

.PHONY: test-local
test-local: ## Run backend tests locally (not in Docker)
	cd backend && bash scripts/test.sh

.PHONY: test-e2e
test-e2e: ## Run end-to-end tests
	bash scripts/test_e2e.sh

# ============================================================================
# LLM Agent Targets
# ============================================================================

.PHONY: agent-evals
agent-evals: ## Run agent evaluations on recent traces
	@echo "Running agent evaluations..."
	docker compose exec backend uv run python -m app.evaluation.cli
	@echo ""
	@echo "Evaluation complete! Reports are in the container at /app/reports/"
	@echo "To copy reports to host: docker compose cp backend:/app/reports ./backend"

.PHONY: agent-evals-no-report
agent-evals-no-report: ## Run agent evaluations without generating report file
	@echo "Running agent evaluations (no report file)..."
	docker compose exec backend uv run python -m app.evaluation.cli --no-report

.PHONY: test-agents
test-agents: ## Run agent-specific tests
	@echo "Running agent unit tests..."
	docker compose exec backend uv run pytest tests/unit/test_agent*.py -v
	@echo ""
	@echo "Running agent API tests..."
	docker compose exec backend uv run pytest tests/api/routes/test_agent.py -v

.PHONY: up-observability
up-observability: ## Start observability stack (Langfuse, Prometheus, Grafana)
	@echo "Starting observability stack..."
	docker compose up -d langfuse-db langfuse prometheus grafana
	@echo ""
	@echo "Observability services started:"
	@echo "  - Langfuse UI:   http://localhost:3001"
	@echo "  - Grafana:       http://localhost:3002 (admin/admin)"
	@echo "  - Prometheus:    http://localhost:9090"

.PHONY: down-observability
down-observability: ## Stop observability stack
	@echo "Stopping observability stack..."
	docker compose stop langfuse langfuse-db prometheus grafana

.PHONY: logs-observability
logs-observability: ## View logs from observability services
	docker compose logs -f langfuse prometheus grafana

.PHONY: agent-dev
agent-dev: up-observability ## Start full stack with observability for agent development
	@echo "Starting full development stack with observability..."
	docker compose up -d
	@echo ""
	@echo "Development stack ready:"
	@echo "  - Frontend:      http://localhost:5173"
	@echo "  - Backend API:   http://localhost:8000"
	@echo "  - API Docs:      http://localhost:8000/docs"
	@echo "  - Langfuse UI:   http://localhost:3001"
	@echo "  - Grafana:       http://localhost:3002"
	@echo "  - Prometheus:    http://localhost:9090"

# ============================================================================
# Code Quality
# ============================================================================

.PHONY: format
format: ## Format backend code
	docker compose exec backend bash scripts/format.sh

.PHONY: lint
lint: ## Lint backend code
	docker compose exec backend bash scripts/lint.sh

.PHONY: format-local
format-local: ## Format backend code locally (not in Docker)
	cd backend && bash scripts/format.sh

.PHONY: lint-local
lint-local: ## Lint backend code locally (not in Docker)
	cd backend && bash scripts/lint.sh

# ============================================================================
# Deployment
# ============================================================================

.PHONY: build-images
build-images: ## Build production Docker images
	bash scripts/build.sh

.PHONY: push-images
push-images: ## Build and push Docker images to registry
	bash scripts/build-push.sh

.PHONY: deploy
deploy: ## Deploy to production (requires configuration)
	bash scripts/deploy.sh

# ============================================================================
# Monitoring and Observability
# ============================================================================

.PHONY: metrics
metrics: ## View Prometheus metrics from backend
	@curl -s http://localhost:8000/metrics | head -50
	@echo ""
	@echo "... (showing first 50 lines)"
	@echo "Full metrics available at: http://localhost:8000/metrics"

.PHONY: health
health: ## Check health of all services
	@echo "Checking service health..."
	@echo ""
	@echo "Backend API:"
	@curl -s http://localhost:8000/api/v1/utils/health-check | jq . 2>/dev/null || curl -s http://localhost:8000/api/v1/utils/health-check
	@echo ""
	@echo "Frontend:"
	@curl -s -o /dev/null -w "Status: %{http_code}\n" http://localhost:5173
	@echo ""
	@echo "Langfuse:"
	@curl -s -o /dev/null -w "Status: %{http_code}\n" http://localhost:3001
	@echo ""
	@echo "Grafana:"
	@curl -s -o /dev/null -w "Status: %{http_code}\n" http://localhost:3002

# ============================================================================
# Database Management
# ============================================================================

.PHONY: db-shell
db-shell: ## Open PostgreSQL shell
	docker compose exec db psql -U app -d app

.PHONY: db-backup
db-backup: ## Backup database to backups/ directory
	@mkdir -p backups
	@BACKUP_FILE="backups/backup_$$(date +%Y%m%d_%H%M%S).sql"; \
	docker compose exec -T db pg_dump -U app -d app > $$BACKUP_FILE; \
	echo "Database backed up to $$BACKUP_FILE"

.PHONY: db-restore
db-restore: ## Restore database from backup (use FILE=path/to/backup.sql)
	@if [ -z "$(FILE)" ]; then \
		echo "Error: FILE is required. Usage: make db-restore FILE=backups/backup.sql"; \
		exit 1; \
	fi
	@if [ ! -f "$(FILE)" ]; then \
		echo "Error: File $(FILE) not found"; \
		exit 1; \
	fi
	docker compose exec -T db psql -U app -d app < $(FILE)
	@echo "Database restored from $(FILE)"

# ============================================================================
# Redis Management
# ============================================================================

.PHONY: redis-cli
redis-cli: ## Open Redis CLI
	docker compose exec redis redis-cli

.PHONY: redis-flush
redis-flush: ## Flush all Redis data (rate limiting state)
	@echo "Flushing Redis data..."
	docker compose exec redis redis-cli FLUSHALL
	@echo "Redis data cleared"

# ============================================================================
# Utility Targets
# ============================================================================

.PHONY: env-example
env-example: ## Show environment variable examples
	@cat .env.example

.PHONY: urls
urls: ## Display URLs for all services
	@echo "Service URLs:"
	@echo "  - Frontend:      http://localhost:5173"
	@echo "  - Backend API:   http://localhost:8000"
	@echo "  - API Docs:      http://localhost:8000/docs"
	@echo "  - Langfuse UI:   http://localhost:3001"
	@echo "  - Grafana:       http://localhost:3002 (admin/admin)"
	@echo "  - Prometheus:    http://localhost:9090"
	@echo "  - Adminer:       http://localhost:8080"
	@echo "  - Traefik:       http://localhost:8090"

.PHONY: install
install: ## Install dependencies (first-time setup)
	@echo "Installing backend dependencies..."
	cd backend && uv sync
	@echo ""
	@echo "Installing frontend dependencies..."
	cd frontend && npm install
	@echo ""
	@echo "Setup complete! You can now run 'make up' to start the stack."

# Default target
.DEFAULT_GOAL := help
