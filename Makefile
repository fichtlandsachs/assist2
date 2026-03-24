.PHONY: up down logs migrate makemigrations test shell format lint help

COMPOSE_FILE = infra/docker-compose.yml
COMPOSE_DEV_FILE = infra/docker-compose.dev.yml
BACKEND_CONTAINER = backend

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Start all services (production)
	docker compose -f $(COMPOSE_FILE) up -d

up-dev: ## Start all services (development with hot reload)
	docker compose -f $(COMPOSE_FILE) -f $(COMPOSE_DEV_FILE) up -d

down: ## Stop all services
	docker compose -f $(COMPOSE_FILE) down

down-dev: ## Stop all dev services
	docker compose -f $(COMPOSE_FILE) -f $(COMPOSE_DEV_FILE) down

logs: ## Show logs for all services
	docker compose -f $(COMPOSE_FILE) logs -f

logs-backend: ## Show backend logs only
	docker compose -f $(COMPOSE_FILE) logs -f $(BACKEND_CONTAINER)

migrate: ## Run database migrations (alembic upgrade head)
	docker compose -f $(COMPOSE_FILE) exec $(BACKEND_CONTAINER) alembic upgrade head

makemigrations: ## Generate new migration (alembic revision --autogenerate)
	docker compose -f $(COMPOSE_FILE) exec $(BACKEND_CONTAINER) alembic revision --autogenerate -m "$(msg)"

test: ## Run test suite with pytest
	docker compose -f $(COMPOSE_FILE) exec $(BACKEND_CONTAINER) pytest tests/ -v --cov=app --cov-report=term-missing

test-unit: ## Run only unit tests
	docker compose -f $(COMPOSE_FILE) exec $(BACKEND_CONTAINER) pytest tests/unit/ -v

test-integration: ## Run only integration tests
	docker compose -f $(COMPOSE_FILE) exec $(BACKEND_CONTAINER) pytest tests/integration/ -v

shell: ## Open bash shell in backend container
	docker compose -f $(COMPOSE_FILE) exec $(BACKEND_CONTAINER) bash

format: ## Format code with ruff
	docker compose -f $(COMPOSE_FILE) exec $(BACKEND_CONTAINER) ruff format app/ tests/

lint: ## Lint code with ruff
	docker compose -f $(COMPOSE_FILE) exec $(BACKEND_CONTAINER) ruff check app/ tests/

build: ## Build all Docker images
	docker compose -f $(COMPOSE_FILE) build

build-no-cache: ## Build all Docker images without cache
	docker compose -f $(COMPOSE_FILE) build --no-cache

ps: ## Show running containers
	docker compose -f $(COMPOSE_FILE) ps

restart-backend: ## Restart backend service
	docker compose -f $(COMPOSE_FILE) restart $(BACKEND_CONTAINER)

seed: ## Seed initial data (system roles and permissions)
	docker compose -f $(COMPOSE_FILE) exec $(BACKEND_CONTAINER) python -m app.scripts.seed
