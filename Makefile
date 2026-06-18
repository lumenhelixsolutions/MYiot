# =============================================================================
# MYiot — Universal Smart Home Hub
# Makefile for common development tasks
# =============================================================================
# Colors (MYiot brand palette)
# Indigo:  #6366F1  |  Cyan: #06B6D4  |  Amber: #F59E0B
# =============================================================================

.DEFAULT_GOAL := help

# Directories
FRONTEND_DIR := frontend
BACKEND_DIR := backend

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "  \033[38;2;99;102;241m\033[1mMYiot\033[0m \033[38;2;6;182;212m— Universal Smart Home Hub\033[0m"
	@echo ""
	@echo "  \033[38;2;245;158;11mUsage:\033[0m make \033[38;2;6;182;212m<command>\033[0m"
	@echo ""
	@echo "  \033[1mDevelopment:\033[0m"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[38;2;6;182;212m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------
.PHONY: install
install: ## Install all dependencies (frontend + backend)
	@echo "  \033[38;2;99;102;241m\033[1m→ Installing MYiot dependencies...\033[0m"
	@echo ""
	@echo "  \033[38;2;6;182;212m  [1/2] Frontend (npm)...\033[0m"
	@cd $(FRONTEND_DIR) && npm install
	@echo "  \033[38;2;34;197;94m  ✓ Frontend dependencies installed\033[0m"
	@echo ""
	@echo "  \033[38;2;6;182;212m  [2/2] Backend (pip)...\033[0m"
	@cd $(BACKEND_DIR) && python3 -m venv .venv || true
	@cd $(BACKEND_DIR) && . .venv/bin/activate && pip install -e ".[dev]"
	@echo "  \033[38;2;34;197;94m  ✓ Backend dependencies installed\033[0m"
	@echo ""
	@echo "  \033[38;2;34;197;94m\033[1m✓ All dependencies installed!\033[0m"

# ---------------------------------------------------------------------------
# Development Servers
# ---------------------------------------------------------------------------
.PHONY: dev dev-frontend dev-backend
dev: ## Start both frontend and backend dev servers (requires tmux or two terminals)
	@echo "  \033[38;2;245;158;11m⚠ Start frontend and backend in separate terminals:\033[0m"
	@echo "    Terminal 1: make dev-frontend"
	@echo "    Terminal 2: make dev-backend"

dev-frontend: ## Start frontend development server (Vite)
	@echo "  \033[38;2;99;102;241m\033[1m→ Starting frontend dev server...\033[0m"
	@cd $(FRONTEND_DIR) && npm run dev

dev-backend: ## Start backend development server (uvicorn + reload)
	@echo "  \033[38;2;99;102;241m\033[1m→ Starting backend dev server...\033[0m"
	@cd $(BACKEND_DIR) && . .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------
.PHONY: build build-frontend build-backend
build: build-frontend build-backend ## Build all production assets

build-frontend: ## Build frontend for production
	@echo "  \033[38;2;99;102;241m\033[1m→ Building frontend...\033[0m"
	@cd $(FRONTEND_DIR) && npm run build
	@echo "  \033[38;2;34;197;94m  ✓ Frontend build complete\033[0m"

build-backend: ## Build backend (verify + compile)
	@echo "  \033[38;2;99;102;241m\033[1m→ Building backend...\033[0m"
	@cd $(BACKEND_DIR) && . .venv/bin/activate && pybabel compile -d translations || true
	@echo "  \033[38;2;34;197;94m  ✓ Backend build complete\033[0m"

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------
.PHONY: test test-frontend test-backend test-e2e
test: test-frontend test-backend ## Run all test suites

test-frontend: ## Run frontend tests (Jest + React Testing Library)
	@echo "  \033[38;2;99;102;241m\033[1m→ Running frontend tests...\033[0m"
	@cd $(FRONTEND_DIR) && npm run test:run

test-backend: ## Run backend tests (pytest)
	@echo "  \033[38;2;99;102;241m\033[1m→ Running backend tests...\033[0m"
	@cd $(BACKEND_DIR) && . .venv/bin/activate && pytest -xvs --cov=app --cov-report=term-missing

test-e2e: ## Run end-to-end tests (Playwright)
	@echo "  \033[38;2;99;102;241m\033[1m→ Running E2E tests...\033[0m"
	@cd $(FRONTEND_DIR) && npx playwright test

# ---------------------------------------------------------------------------
# Linting
# ---------------------------------------------------------------------------
.PHONY: lint lint-frontend lint-backend
lint: lint-frontend lint-backend ## Run all linters

lint-frontend: ## Lint frontend (ESLint + Prettier check)
	@echo "  \033[38;2;99;102;241m\033[1m→ Linting frontend...\033[0m"
	@cd $(FRONTEND_DIR) && npm run lint

lint-backend: ## Lint backend (Ruff + mypy)
	@echo "  \033[38;2;99;102;241m\033[1m→ Linting backend...\033[0m"
	@cd $(BACKEND_DIR) && . .venv/bin/activate && ruff check app tests && mypy app

# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
.PHONY: format format-frontend format-backend
format: format-frontend format-backend ## Run all formatters

format-frontend: ## Format frontend (Prettier)
	@echo "  \033[38;2;99;102;241m\033[1m→ Formatting frontend...\033[0m"
	@cd $(FRONTEND_DIR) && npm run format

format-backend: ## Format backend (Ruff + Black)
	@echo "  \033[38;2;99;102;241m\033[1m→ Formatting backend...\033[0m"
	@cd $(BACKEND_DIR) && . .venv/bin/activate && ruff format app tests && ruff check --fix app tests

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------
.PHONY: docker-build docker-up docker-down docker-logs docker-clean
docker-build: ## Build the Docker image
	@echo "  \033[38;2;99;102;241m\033[1m→ Building MYiot Docker image...\033[0m"
	@docker build -t myiot:latest .

docker-up: ## Start all services with docker-compose
	@echo "  \033[38;2;99;102;241m\033[1m→ Starting MYiot services...\033[0m"
	@docker compose up -d

docker-down: ## Stop all services
	@echo "  \033[38;2;245;158;11m\033[1m→ Stopping MYiot services...\033[0m"
	@docker compose down

docker-logs: ## Follow logs from all services
	@docker compose logs -f

docker-clean: ## Remove containers, volumes, and images
	@echo "  \033[38;2;245;158;11m\033[1m→ Cleaning Docker resources...\033[0m"
	@docker compose down -v --rmi local

# ---------------------------------------------------------------------------
# Production Deployment
# ---------------------------------------------------------------------------
.PHONY: deploy-prod
deploy-prod: ## Deploy production stack with Traefik + SSL
	@echo "  \033[38;2;99;102;241m\033[1m→ Deploying MYiot production stack...\033[0m"
	@docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
.PHONY: clean
clean: ## Clean build artifacts, caches, and generated files
	@echo "  \033[38;2;245;158;11m\033[1m→ Cleaning build artifacts...\033[0m"
	@cd $(FRONTEND_DIR) && rm -rf dist node_modules/.cache
	@cd $(BACKEND_DIR) && rm -rf __pycache__ .pytest_cache .mypy_cache .coverage htmlcov
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@echo "  \033[38;2;34;197;94m  ✓ Cleanup complete\033[0m"

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
.PHONY: info update check-licenses
info: ## Display project information and versions
	@echo ""
	@echo "  \033[38;2;99;102;241m\033[1mMYiot\033[0m \033[38;2;6;182;212m— System Information\033[0m"
	@echo ""
	@echo "  \033[1mFrontend:\033[0m"
	@cd $(FRONTEND_DIR) && echo "    Node.js:    $$(node --version 2>/dev/null || echo 'N/A')"
	@cd $(FRONTEND_DIR) && echo "    npm:        $$(npm --version 2>/dev/null || echo 'N/A')"
	@echo ""
	@echo "  \033[1mBackend:\033[0m"
	@echo "    Python:     $$(python3 --version 2>/dev/null || echo 'N/A')"
	@cd $(BACKEND_DIR) && echo "    pip:        $$(. .venv/bin/activate && pip --version 2>/dev/null || echo 'N/A')"
	@echo ""
	@echo "  \033[1mDocker:\033[0m"
	@echo "    Docker:     $$(docker --version 2>/dev/null || echo 'N/A')"
	@echo "    Compose:    $$(docker compose version 2>/dev/null || echo 'N/A')"
	@echo ""

update: ## Update all dependencies to latest compatible versions
	@echo "  \033[38;2;99;102;241m\033[1m→ Updating dependencies...\033[0m"
	@cd $(FRONTEND_DIR) && npm update
	@cd $(BACKEND_DIR) && . .venv/bin/activate && pip install -e ".[dev]" --upgrade
	@echo "  \033[38;2;34;197;94m  ✓ Dependencies updated\033[0m"

check-licenses: ## Check for license compliance
	@echo "  \033[38;2;99;102;241m\033[1m→ Checking licenses...\033[0m"
	@cd $(FRONTEND_DIR) && npm run check-licenses 2>/dev/null || echo "    No license check configured"
	@cd $(BACKEND_DIR) && . .venv/bin/activate && pip-licenses 2>/dev/null || echo "    pip-licenses not installed"
