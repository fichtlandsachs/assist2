.PHONY: up down logs migrate makemigrations test shell format lint help

COMPOSE_FILE = infra/docker-compose.yml
COMPOSE_DEV_FILE = infra/docker-compose.dev.yml
COMPOSE_ENV_FILE = infra/.env
BACKEND_CONTAINER = backend

COMPOSE = docker compose --env-file $(COMPOSE_ENV_FILE) -f $(COMPOSE_FILE)
COMPOSE_DEV = docker compose --env-file $(COMPOSE_ENV_FILE) -f $(COMPOSE_FILE) -f $(COMPOSE_DEV_FILE)

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Start all services (production)
	$(COMPOSE) up -d

up-dev: ## Start all services (development with hot reload)
	$(COMPOSE_DEV) up -d

down: ## Stop all services
	$(COMPOSE) down

down-dev: ## Stop all dev services
	$(COMPOSE_DEV) down

logs: ## Show logs for all services
	$(COMPOSE) logs -f

logs-backend: ## Show backend logs only
	$(COMPOSE) logs -f $(BACKEND_CONTAINER)

migrate: ## Run database migrations (alembic upgrade head)
	$(COMPOSE) exec $(BACKEND_CONTAINER) alembic upgrade head

makemigrations: ## Generate new migration (alembic revision --autogenerate)
	$(COMPOSE) exec $(BACKEND_CONTAINER) alembic revision --autogenerate -m "$(msg)"

test: ## Run test suite with pytest
	$(COMPOSE) exec $(BACKEND_CONTAINER) pytest tests/ -v --cov=app --cov-report=term-missing

test-unit: ## Run only unit tests
	$(COMPOSE) exec $(BACKEND_CONTAINER) pytest tests/unit/ -v

test-integration: ## Run only integration tests
	$(COMPOSE) exec $(BACKEND_CONTAINER) pytest tests/integration/ -v

shell: ## Open bash shell in backend container
	$(COMPOSE) exec $(BACKEND_CONTAINER) bash

format: ## Format code with ruff
	$(COMPOSE) exec $(BACKEND_CONTAINER) ruff format app/ tests/

lint: ## Lint code with ruff
	$(COMPOSE) exec $(BACKEND_CONTAINER) ruff check app/ tests/

build: ## Build all Docker images
	$(COMPOSE) build

build-no-cache: ## Build all Docker images without cache
	$(COMPOSE) build --no-cache

ps: ## Show running containers
	$(COMPOSE) ps

restart-backend: ## Restart backend service
	$(COMPOSE) restart $(BACKEND_CONTAINER)

seed: ## Seed initial data (system roles and permissions)
	$(COMPOSE) exec $(BACKEND_CONTAINER) python -m app.scripts.seed
