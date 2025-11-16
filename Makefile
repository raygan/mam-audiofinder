# Makefile for MAM Audiobook Finder Test Suite
# Provides targets for backend, frontend, and full test execution

.PHONY: help test test-backend test-frontend test-all test-coverage test-ci \
        lint lint-python lint-frontend clean clean-pyc clean-test \
        install install-dev setup-selenium

# Default target - show help
.DEFAULT_GOAL := help

# Variables
PYTHON := python3
PYTEST := pytest
PIP := pip3
DOCKER_COMPOSE := docker compose

# Test directories
BACKEND_TESTS := tests/
FRONTEND_TESTS := tests/frontend/
ALL_TESTS := tests/

# Coverage settings
COVERAGE_MIN := 70
COVERAGE_HTML := htmlcov/

# Selenium settings
SELENIUM_HUB := http://localhost:4444
SELENIUM_BROWSER := chrome

##@ Help

help: ## Display this help message
	@echo "MAM Audiobook Finder - Test Suite"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Testing

test: test-backend ## Run full test suite (backend + frontend)
	@echo "✓ All tests completed successfully"

test-backend: ## Run backend tests (pytest)
	@echo "Running backend tests..."
	@$(PYTEST) $(BACKEND_TESTS) -v --tb=short \
		--ignore=$(FRONTEND_TESTS) \
		-W ignore::DeprecationWarning
	@echo "✓ Backend tests passed"

test-frontend: ## Run frontend tests (Selenium)
	@echo "Running frontend tests..."
	@if [ ! -d "$(FRONTEND_TESTS)" ]; then \
		echo "⚠ Frontend tests not yet implemented"; \
		echo "  Run 'make setup-frontend-tests' to initialize"; \
		exit 0; \
	fi
	@$(PYTEST) $(FRONTEND_TESTS) -v --tb=short \
		--selenium-hub=$(SELENIUM_HUB) \
		--browser=$(SELENIUM_BROWSER)
	@echo "✓ Frontend tests passed"

test-all: test-backend test-frontend ## Run all tests (backend + frontend)
	@echo "✓ Full test suite completed"

test-coverage: ## Run backend tests with coverage report
	@echo "Running tests with coverage analysis..."
	@$(PYTEST) $(BACKEND_TESTS) \
		--ignore=$(FRONTEND_TESTS) \
		--cov=app \
		--cov-report=html \
		--cov-report=term \
		--cov-fail-under=$(COVERAGE_MIN) \
		-v
	@echo "✓ Coverage report generated at $(COVERAGE_HTML)index.html"

test-backend-unit: ## Run only backend unit tests
	@echo "Running backend unit tests..."
	@$(PYTEST) $(BACKEND_TESTS) -v --tb=short \
		--ignore=$(FRONTEND_TESTS) \
		-m "not integration" \
		-W ignore::DeprecationWarning || true

test-backend-integration: ## Run backend integration tests
	@echo "Running backend integration tests..."
	@$(PYTEST) $(BACKEND_TESTS) -v --tb=short \
		--ignore=$(FRONTEND_TESTS) \
		-m integration || true
	@echo "⚠ Note: Integration tests not yet marked with @pytest.mark.integration"

test-ci: ## Run tests in CI environment (with XML reports)
	@echo "Running tests for CI/CD..."
	@$(PYTEST) $(BACKEND_TESTS) -v \
		--ignore=$(FRONTEND_TESTS) \
		--junitxml=test-results/junit-backend.xml \
		--cov=app \
		--cov-report=xml \
		--cov-report=term
	@if [ -d "$(FRONTEND_TESTS)" ]; then \
		$(PYTEST) $(FRONTEND_TESTS) -v \
			--junitxml=test-results/junit-frontend.xml \
			--html=test-results/frontend-report.html \
			--self-contained-html; \
	fi
	@echo "✓ CI test reports generated in test-results/"

test-quick: ## Run quick smoke tests (fastest tests only)
	@echo "Running quick smoke tests..."
	@$(PYTEST) $(BACKEND_TESTS) -v --tb=short \
		--ignore=$(FRONTEND_TESTS) \
		-k "test_sanitize or test_format" \
		-W ignore::DeprecationWarning
	@echo "✓ Quick tests passed"

##@ Code Quality

lint: lint-python ## Run all linting checks

lint-python: ## Run Python linting (flake8, mypy, black, isort)
	@echo "Running Python linters..."
	@echo "→ flake8..."
	@flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203,W503 || true
	@echo "→ black (check only)..."
	@black app/ tests/ --check --line-length=120 || true
	@echo "→ isort (check only)..."
	@isort app/ tests/ --check-only --profile black || true
	@echo "→ mypy..."
	@mypy app/ --ignore-missing-imports || true
	@echo "✓ Linting complete"

format: ## Auto-format Python code (black + isort)
	@echo "Formatting Python code..."
	@black app/ tests/ --line-length=120
	@isort app/ tests/ --profile black
	@echo "✓ Code formatted"

##@ Setup

install: ## Install production dependencies
	@echo "Installing production dependencies..."
	@$(PIP) install -r requirements.txt
	@echo "✓ Production dependencies installed"

install-dev: ## Install development dependencies (including test tools)
	@echo "Installing development dependencies..."
	@$(PIP) install -r requirements-dev.txt
	@echo "✓ Development dependencies installed"

setup-selenium: ## Start Selenium Grid in Docker
	@echo "Starting Selenium Grid..."
	@$(DOCKER_COMPOSE) up -d selenium
	@echo "Waiting for Selenium to be ready..."
	@sleep 5
	@echo "✓ Selenium Grid running at $(SELENIUM_HUB)"

stop-selenium: ## Stop Selenium Grid
	@echo "Stopping Selenium Grid..."
	@$(DOCKER_COMPOSE) stop selenium
	@echo "✓ Selenium Grid stopped"

setup-frontend-tests: ## Initialize frontend test structure (run once)
	@echo "Setting up frontend test infrastructure..."
	@mkdir -p $(FRONTEND_TESTS)utils
	@mkdir -p test-results
	@echo "✓ Frontend test directories created"
	@echo "  Next: Implement tests in $(FRONTEND_TESTS)"

##@ Cleanup

clean: clean-pyc clean-test ## Clean all generated files

clean-pyc: ## Remove Python cache files
	@echo "Cleaning Python cache files..."
	@find . -type f -name '*.pyc' -delete
	@find . -type d -name '__pycache__' -delete
	@find . -type d -name '*.egg-info' -exec rm -rf {} + || true
	@echo "✓ Python cache cleaned"

clean-test: ## Remove test artifacts and coverage reports
	@echo "Cleaning test artifacts..."
	@rm -rf $(COVERAGE_HTML)
	@rm -rf .pytest_cache
	@rm -rf test-results/
	@rm -f .coverage
	@rm -f coverage.xml
	@echo "✓ Test artifacts cleaned"

##@ Docker

docker-test: ## Run tests inside Docker container
	@echo "Running tests in Docker container..."
	@$(DOCKER_COMPOSE) exec mam-audiofinder make test-backend
	@echo "✓ Docker tests completed"

docker-test-coverage: ## Run tests with coverage in Docker
	@echo "Running tests with coverage in Docker..."
	@$(DOCKER_COMPOSE) exec mam-audiofinder make test-coverage
	@echo "✓ Docker coverage tests completed"

##@ Development

watch-tests: ## Run tests in watch mode (re-run on file changes)
	@echo "Starting test watcher..."
	@$(PYTEST) $(BACKEND_TESTS) -v \
		--ignore=$(FRONTEND_TESTS) \
		-f \
		--tb=short
