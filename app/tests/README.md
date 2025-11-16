# Tests Directory

This directory contains all test files for the MAM Audiobook Finder application.

## Running Tests

### Inside Docker Container

```bash
# Enter the running container
docker exec -it mam-audiofinder bash

# Run all pytest tests
cd /app
pytest tests/ -v

# Run specific test file
pytest tests/test_search.py -v

# Run the description fetch integration test
python3 tests/test_description_fetch.py
```

### From Host (Using Makefile)

```bash
# Run backend tests
make test-backend

# Run with coverage
make test-coverage

# Run quick smoke tests
make test-quick

# Run tests inside Docker via make
make docker-test
```

## Test Files

- `test_search.py` - Search functionality tests
- `test_covers.py` - Cover caching and management tests
- `test_verification.py` - ABS import verification tests
- `test_helpers.py` - Utility function tests
- `test_migration_syntax.py` - Database migration syntax validation
- `test_description_fetch.py` - Integration test for description fetching (run manually)
- `conftest.py` - Pytest fixtures and configuration
- `check_db_schema.py` - Database schema validation utility

## Database Paths

Tests inside the container use:
- `/data/history.db` - History database
- `/data/covers.db` - Covers cache database

These paths are mounted from the host `DATA_DIR` specified in docker-compose.yml.

## Frontend Tests

Frontend tests are located in `frontend/` subdirectory and can be run with Selenium Grid.

See the main project CLAUDE.md for more testing details.
