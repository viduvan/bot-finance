# ============================================================
# ACTA - Makefile
# ============================================================

.PHONY: help up down restart logs backend-logs db-migrate db-upgrade test lint clean setup

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Docker ───────────────────────────────────────────────────

up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

restart: ## Restart all services
	docker compose restart

logs: ## Follow all logs
	docker compose logs -f

backend-logs: ## Follow backend logs
	docker compose logs -f backend

worker-logs: ## Follow Celery worker logs
	docker compose logs -f celery-worker

build: ## Build all images
	docker compose build

# ── Database ─────────────────────────────────────────────────

db-migrate: ## Create a new migration (usage: make db-migrate msg="description")
	cd apps/backend && alembic revision --autogenerate -m "$(msg)"

db-upgrade: ## Apply all pending migrations
	cd apps/backend && alembic upgrade head

db-downgrade: ## Rollback last migration
	cd apps/backend && alembic downgrade -1

db-reset: ## Drop and recreate database (DESTRUCTIVE)
	docker compose exec postgres psql -U acta -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	cd apps/backend && alembic upgrade head

# ── Testing ──────────────────────────────────────────────────

test: ## Run all tests
	cd apps/backend && python -m pytest tests/ -v

test-unit: ## Run unit tests only
	cd apps/backend && python -m pytest tests/unit/ -v

test-integration: ## Run integration tests
	cd apps/backend && python -m pytest tests/integration/ -v

test-security: ## Run security tests
	cd apps/backend && python -m pytest tests/security/ -v

test-cov: ## Run tests with coverage report
	cd apps/backend && python -m pytest tests/ -v --cov=app --cov-report=html --cov-report=term

# ── Code Quality ─────────────────────────────────────────────

lint: ## Run linter
	cd apps/backend && ruff check app/ tests/

lint-fix: ## Run linter with auto-fix
	cd apps/backend && ruff check app/ tests/ --fix

format: ## Format code
	cd apps/backend && ruff format app/ tests/

typecheck: ## Run type checker
	cd apps/backend && mypy app/

# ── Development ──────────────────────────────────────────────

dev: ## Run backend in development mode (without Docker)
	cd apps/backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Run frontend dev server
	cd apps/frontend && npm run dev

shell: ## Open Python shell in backend container
	docker compose exec backend python -c "import IPython; IPython.start_ipython()" 2>/dev/null || docker compose exec backend python

# ── Setup ────────────────────────────────────────────────────

setup: ## Initial project setup
	cp .env.example .env
	docker compose up -d postgres redis
	sleep 5
	cd apps/backend && pip install -e ".[dev]"
	cd apps/backend && alembic upgrade head
	@echo "✅ Setup complete! Run 'make up' to start all services."

create-admin: ## Create admin user
	cd apps/backend && python scripts/create_admin.py

pull-model: ## Pull Ollama model
	docker compose exec ollama ollama pull qwen2.5:14b

# ── Cleanup ──────────────────────────────────────────────────

clean: ## Remove all containers, volumes, and build artifacts
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
