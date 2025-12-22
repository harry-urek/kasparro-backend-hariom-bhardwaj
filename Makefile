.PHONY: help install dev build up down restart logs clean test lint format

# Variables
COMPOSE=docker-compose
PYTHON=python3
PIP=pip3

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies locally
	$(PIP) install -r requirements.txt

dev: ## Run the application locally (without Docker)
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

build: ## Build Docker images
	$(COMPOSE) build

up: ## Start all services
	$(COMPOSE) up -d

down: ## Stop all services
	$(COMPOSE) down

restart: down up ## Restart all services

logs: ## View logs from all services
	$(COMPOSE) logs -f

logs-api: ## View logs from API service only
	$(COMPOSE) logs -f api

ps: ## List running containers
	$(COMPOSE) ps

shell: ## Open a shell in the API container
	$(COMPOSE) exec api /bin/bash

clean: ## Remove containers, volumes, and images
	$(COMPOSE) down -v --remove-orphans
	docker system prune -f

test: ## Run tests (placeholder for future tests)
	@echo "Tests not yet implemented"
	# $(PYTHON) -m pytest tests/

lint: ## Run linting (placeholder)
	@echo "Linting not yet configured"
	# $(PYTHON) -m ruff check app/

format: ## Format code (placeholder)
	@echo "Formatting not yet configured"
	# $(PYTHON) -m ruff format app/

health: ## Check API health
	@curl -s http://localhost:8000/health | python -m json.tool || echo "API not responding"

data: ## Test /data endpoint
	@curl -s "http://localhost:8000/data?page=1&page_size=10" | python -m json.tool || echo "API not responding"
