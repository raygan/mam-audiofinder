# Testing Guide for MAM Audiobook Finder

This document describes the testing infrastructure and how to run tests for the MAM Audiobook Finder project.

## Overview

The project uses a **Makefile-based test suite** with three main test categories:

1. **Backend Tests** - Python/FastAPI tests using pytest (120+ tests)
2. **Frontend Tests** - Selenium-based browser tests (50+ tests)
3. **Full Test Suite** - Combined backend + frontend tests

## Quick Start

```bash
# 1. Create and activate virtual environment (recommended)
make venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# 2. Install development dependencies
make install-dev

# 3. Run backend tests only
make test-backend

# 4. Run frontend tests only (requires Selenium)
make test-frontend

# 5. Run all tests
make test-all

# Show all available targets
make help
```

**Note:** If you're on Debian/Ubuntu and get an "externally-managed-environment" error, you **must** create a virtual environment first using `make venv`.

## Test Architecture

### Backend Tests (`tests/`)

**Location:** `tests/` (excludes `tests/frontend/`)
**Framework:** pytest + pytest-asyncio + pytest-mock
**Coverage:** ~120 test cases

**Test Files:**
- `test_search.py` - Search functionality, MAM API integration (40 tests)
- `test_covers.py` - Cover caching, cleanup, download (30 tests)
- `test_verification.py` - Audiobookshelf verification (25 tests)
- `test_helpers.py` - Utility functions (25 tests)
- `test_migration_syntax.py` - Database migration validation

**Key Features:**
- In-memory SQLite for isolation
- Mock HTTP clients for external APIs
- Comprehensive fixtures in `conftest.py`
- Async endpoint testing

### Frontend Tests (`tests/frontend/`)

**Location:** `tests/frontend/`
**Framework:** Selenium WebDriver + pytest-selenium
**Coverage:** ~50 test cases (many marked with `@pytest.mark.skip` pending full environment)

**Test Files:**
- `test_search_page.py` - Search UI, results, add to qBittorrent
- `test_history_page.py` - History table, status updates, delete
- `test_showcase_page.py` - Grid view, filtering, detail modal
- `test_import_workflow.py` - End-to-end workflows

**Architecture:**
- **Page Object Model (POM)** pattern for maintainability
- Base page class with common methods
- Dedicated page classes for each route
- Helper utilities for waits and assertions

**Infrastructure:**
- `conftest.py` - WebDriver setup, fixtures, screenshot on failure
- `utils/page_objects.py` - Page Object Model classes
- `utils/helpers.py` - Test utilities and wait helpers

## Running Tests

### Backend Tests

```bash
# All backend tests
make test-backend

# With verbose output
make test-backend PYTEST_ARGS="-v"

# Run specific test file
pytest tests/test_search.py -v

# Run specific test
pytest tests/test_search.py::test_sanitize -v

# Run with coverage
make test-coverage

# Quick smoke tests only
make test-quick
```

### Frontend Tests

**Prerequisites:**
1. Application running at `http://localhost:8008` (or set `TEST_BASE_URL`)
2. Selenium Grid running (see [Selenium Setup](#selenium-setup))

```bash
# Start Selenium Grid
make setup-selenium

# Run frontend tests
make test-frontend

# Run with specific browser
make test-frontend BROWSER=firefox

# Run in headless mode (default)
make test-frontend HEADLESS=true

# Run with visible browser
make test-frontend HEADLESS=false

# Run specific frontend test file
pytest tests/frontend/test_search_page.py -v --base-url=http://localhost:8008

# Stop Selenium Grid
make stop-selenium
```

### Full Test Suite

```bash
# Run all tests (backend + frontend)
make test-all

# Or use the shorthand
make test
```

## Selenium Setup

### Option 1: Docker Selenium Grid (Recommended)

```bash
# Start Selenium Grid in Docker
make setup-selenium

# Verify it's running
curl http://localhost:4444/status

# Stop when done
make stop-selenium
```

**Docker Compose Profile:**
```bash
# Start with testing profile
docker compose --profile testing up -d

# This starts both the app and Selenium
```

**VNC Debugging:**
- URL: `http://localhost:7900`
- Password: (none - VNC_NO_PASSWORD=1)
- Watch tests run in real-time

### Option 2: Local WebDriver (Alternative)

Tests will automatically download ChromeDriver/GeckoDriver using `webdriver-manager`:

```bash
# Just run the tests - drivers auto-install
make test-frontend
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEST_BASE_URL` | `http://localhost:8008` | App URL for frontend tests |
| `SELENIUM_HUB` | (none) | Selenium Grid URL (e.g., `http://localhost:4444`) |
| `BROWSER` | `chrome` | Browser to use: `chrome`, `firefox` |
| `HEADLESS` | `true` | Run browser headless: `true`, `false` |

**Set in shell:**
```bash
export TEST_BASE_URL=http://localhost:8008
export BROWSER=firefox
make test-frontend
```

**Or pass to pytest directly:**
```bash
pytest tests/frontend/ --base-url=http://localhost:8008 --browser=chrome --headless=false
```

## Code Quality

### Linting

```bash
# Run all linters
make lint

# Just Python linting
make lint-python

# Individual linters
flake8 app/ tests/
mypy app/ --ignore-missing-imports
black app/ tests/ --check
isort app/ tests/ --check-only
```

### Auto-formatting

```bash
# Format code with black + isort
make format
```

## Coverage Reports

```bash
# Generate HTML coverage report
make test-coverage

# Open report in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

**Coverage Requirements:**
- Minimum: 70%
- Target: 80%+

## CI/CD Integration

```bash
# Generate JUnit XML reports for CI
make test-ci

# Outputs:
# - test-results/junit-backend.xml
# - test-results/junit-frontend.xml
# - test-results/frontend-report.html
# - coverage.xml
```

## Docker Testing

```bash
# Run tests inside Docker container
docker compose up -d
make docker-test

# Run with coverage
make docker-test-coverage
```

## Test Development

### Adding Backend Tests

1. Create test file in `tests/`:
   ```python
   # tests/test_my_feature.py
   import pytest

   def test_my_feature():
       assert True
   ```

2. Use existing fixtures from `tests/conftest.py`

3. Run: `pytest tests/test_my_feature.py -v`

### Adding Frontend Tests

1. Create test file in `tests/frontend/`:
   ```python
   # tests/frontend/test_my_page.py
   from .utils.page_objects import BasePage

   class TestMyPage:
       def test_page_loads(self, driver, base_url):
           page = BasePage(driver, base_url)
           page.navigate_to("/mypage")
           assert "/mypage" in page.get_current_url()
   ```

2. Add page object class in `tests/frontend/utils/page_objects.py` if needed

3. Run: `pytest tests/frontend/test_my_page.py -v --base-url=http://localhost:8008`

### Page Object Model Pattern

**Example:**
```python
from .utils.page_objects import BasePage
from selenium.webdriver.common.by import By

class MyPage(BasePage):
    # Locators
    SUBMIT_BUTTON = (By.ID, "submit")

    def __init__(self, driver, base_url):
        super().__init__(driver, base_url)
        self.navigate_to("/mypage")

    def click_submit(self):
        self.click_element(*self.SUBMIT_BUTTON)
        return self
```

## Troubleshooting

### Backend Tests Fail to Import Modules

**Problem:** `ModuleNotFoundError: No module named 'sqlalchemy'`

**Solution:**
```bash
# Install dev dependencies
pip install -r requirements-dev.txt
```

### Frontend Tests Can't Connect to Selenium

**Problem:** `MaxRetryError: HTTPConnectionPool(host='localhost', port=4444)`

**Solution:**
```bash
# Start Selenium Grid
make setup-selenium

# Verify it's running
curl http://localhost:4444/status
```

### Frontend Tests Can't Find Elements

**Problem:** `TimeoutException: Element not found: By.ID='search-button'`

**Solution:**
1. Check if app is running: `curl http://localhost:8008/health`
2. Increase timeout in test or page object
3. Run with visible browser to debug: `make test-frontend HEADLESS=false`
4. Check screenshot in `test-results/screenshots/`

### Tests Are Slow

**Problem:** Tests taking too long

**Solutions:**
- Run specific test files instead of full suite
- Use `make test-quick` for smoke tests
- Use `pytest -k "test_name"` to run specific tests
- Check for hanging waits or timeouts

### Screenshots Not Captured on Failure

**Problem:** No screenshots in `test-results/screenshots/`

**Solution:**
- Directory is created automatically by conftest.py
- Check that test actually failed (not skipped)
- Verify driver fixture is being used

## Test Markers

### Backend

```bash
# Run only unit tests (future)
pytest tests/ -m "not integration"

# Run only integration tests (future)
pytest tests/ -m integration
```

### Frontend

All frontend tests are automatically marked with `@pytest.mark.frontend`:

```bash
# Run only frontend tests
pytest tests/ -m frontend

# Skip frontend tests
pytest tests/ -m "not frontend"
```

## Performance

### Test Execution Times

**Backend:** ~10-30 seconds (120 tests)
**Frontend:** ~2-5 minutes (50 tests, many skipped pending environment)
**Full Suite:** ~3-6 minutes

### Optimization Tips

1. **Parallel execution** (future):
   ```bash
   pip install pytest-xdist
   pytest tests/ -n auto
   ```

2. **Run changed tests only**:
   ```bash
   pytest tests/ --lf  # Last failed
   pytest tests/ --ff  # Failed first
   ```

3. **Skip slow tests**:
   ```bash
   pytest tests/ -m "not slow"
   ```

## Best Practices

### Backend Testing
- ✅ Use in-memory SQLite for DB tests
- ✅ Mock external API calls
- ✅ Test both success and error cases
- ✅ Use fixtures for common setup
- ✅ Keep tests independent and isolated

### Frontend Testing
- ✅ Use Page Object Model pattern
- ✅ Add explicit waits, not sleep()
- ✅ Test user workflows, not implementation
- ✅ Verify elements before interacting
- ✅ Capture screenshots on failure
- ✅ Use meaningful test names
- ⚠️ Mark tests requiring external services with `@pytest.mark.skip`

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements-dev.txt
      - run: make test-coverage
      - uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml

  frontend:
    runs-on: ubuntu-latest
    services:
      selenium:
        image: selenium/standalone-chrome:latest
        ports:
          - 4444:4444
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements-dev.txt
      - run: make test-frontend SELENIUM_HUB=http://localhost:4444
```

## Resources

- **Pytest Docs:** https://docs.pytest.org/
- **Selenium Docs:** https://www.selenium.dev/documentation/
- **Page Object Model:** https://www.selenium.dev/documentation/test_practices/encouraged/page_object_models/
- **pytest-selenium:** https://pytest-selenium.readthedocs.io/

## Summary

```bash
# Essential commands
make help              # Show all targets
make install-dev       # Install dependencies
make test-backend      # Run backend tests
make setup-selenium    # Start Selenium Grid
make test-frontend     # Run frontend tests
make test-all          # Run all tests
make test-coverage     # Generate coverage report
make lint              # Run linters
make clean             # Clean artifacts
```

For questions or issues with the test suite, please check the [project README](README.md) or create an issue.
