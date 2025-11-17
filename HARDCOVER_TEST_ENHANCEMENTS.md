# Hardcover API Test Enhancements

## Overview

Comprehensive augmentation of Hardcover API testing suite with request counting, rate limiting, field validation, and multiple testing frameworks.

## Changes to `hardcover_client.py`

### Request Counting
- Added class-level counters: `_request_count` and `_cache_hit_count`
- Track total API requests and cache hits across all instances
- New methods:
  - `get_request_count()` - Get total API requests made
  - `get_cache_hit_count()` - Get total cache hits
  - `reset_counters()` - Reset counters (useful for testing)

### New API Methods

#### `search_books_by_author(author_name, limit, fields)`
Search for books by a specific author using GraphQL query with custom field selection.

**Parameters:**
- `author_name` (str): Author name to search for
- `limit` (int): Maximum number of results (default: 10)
- `fields` (List[str]): Fields to retrieve (default: title, description, series_names)

**Returns:** List of book dictionaries with requested fields

**Example:**
```python
books = await hardcover_client.search_books_by_author(
    "Brandon Sanderson",
    limit=10,
    fields=["title", "description", "series_names", "book_series"]
)
```

#### `get_series_by_author(author_name, limit)`
Get series by author name with comprehensive field extraction.

**Parameters:**
- `author_name` (str): Author name to search for
- `limit` (int): Maximum number of results (default: 10)

**Returns:** List of series dictionaries with comprehensive data

**Example:**
```python
series = await hardcover_client.get_series_by_author("Brandon Sanderson", limit=10)
```

## Changes to `test_hardcover_api.py`

### New Test Functions

#### 1. `test_author_series_search(author, limit)`
Tests series search by author name with request counting.
- Default: Brandon Sanderson
- Displays series info including books array
- Tracks API requests and cache hits

#### 2. `test_limit_variations()`
Tests different limit values (1, 5, 10, 20) to validate:
- API respects limit parameter
- Results don't exceed requested limit
- Includes wait logic to avoid rate limiting

#### 3. `test_field_extraction()`
Validates extraction of all expected fields from series data:
- series_id
- series_name
- author_name
- book_count
- readers_count
- books (array)

#### 4. `test_books_by_author(author, limit)`
Tests fetching books by author with different field combinations:
- ["title", "description"]
- ["title", "series_names"]
- ["title", "description", "series_names", "book_series"]

#### 5. `test_series_names_field()`
Specifically tests extraction of `series_names` field from books.
- Shows which books have series information
- Validates data structure

### Testing Frameworks

#### Framework 1: Basic Tests (`test_framework_basic`)
Simple series searches with request counting.
- Tests: Mistborn, Stormlight, Kingkiller
- Resets counters at start
- Reports total requests and timing

#### Framework 2: Author-Focused (`test_framework_author_focused`)
Comprehensive author-based testing.
- Tests multiple authors: Brandon Sanderson, Patrick Rothfuss, Joe Abercrombie
- For each author:
  - Searches series
  - Searches books
- Includes wait logic between requests

#### Framework 3: Field Validation (`test_framework_field_validation`)
Tests various field combinations systematically.
- Tests 6 different field combinations
- Validates field presence in results
- Reports which fields are available

### Helper Functions

#### `print_request_stats(start_count, start_cache, label)`
Prints comprehensive request statistics:
- API requests made in current test
- Cache hits in current test
- Total session requests
- Total session cache hits

#### `wait_between_tests(seconds)`
Adds configurable wait time between tests to avoid rate limiting.
- Default: 1.0 seconds
- Used throughout test suite

### Command-Line Arguments

Enhanced CLI with new options:

```bash
# Test author series search
python test_hardcover_api.py --author "Brandon Sanderson"

# Test limit variations
python test_hardcover_api.py --limits

# Test field extraction
python test_hardcover_api.py --fields

# Run specific framework
python test_hardcover_api.py --framework basic
python test_hardcover_api.py --framework author
python test_hardcover_api.py --framework fields
python test_hardcover_api.py --framework all

# Run all tests (default)
python test_hardcover_api.py
```

## Rate Limiting & Wait Logic

All tests include wait logic to prevent hitting API rate limits:
- 0.5-1.0 second delays between individual requests
- 2.0 second delays between frameworks
- Configurable via `wait_between_tests()` helper

## Request Counting

Every test now includes request statistics showing:
- How many API calls were made
- How many cache hits occurred
- Cumulative session totals

Example output:
```
📊 Author Series Search Statistics:
  API Requests Made:         2
  Cache Hits:                1
  Total Requests (session):  15
  Total Cache Hits (session): 8
```

## Fields Tested

Tests validate availability and structure of:
- **series_names** - Array of series names a book belongs to
- **description** - Book/series description text
- **title** - Book/series title
- **book_series** - Series relationship data
- **list_books** - Books in a list/collection
- **author_name** - Author name(s)
- **book_count** - Number of books in series
- **readers_count** - Popularity metric

## ABS Integration

Note: The current implementation focuses on Hardcover API testing. ABS integration for reducing Hardcover calls can be added by:
1. Checking ABS library first for book metadata
2. Only querying Hardcover if ABS doesn't have the data
3. Caching ABS results to reduce both API calls

This optimization is prepared for but not yet implemented in these tests.

## Running the Enhanced Tests

### In Docker Container
```bash
# All tests
docker exec -it mam-audiofinder python /app/tests/test_hardcover_api.py

# Specific framework
docker exec -it mam-audiofinder python /app/tests/test_hardcover_api.py --framework author

# Author search
docker exec -it mam-audiofinder python /app/tests/test_hardcover_api.py --author "Patrick Rothfuss"
```

### Test Coverage

**Original Tests:** 5 tests
- Configuration
- Series search
- Series books
- Rate limiting
- Caching

**New Tests:** 8 additional tests
- Author series search
- Limit variations
- Field extraction
- Books by author
- Series names field
- Framework: Basic
- Framework: Author-focused
- Framework: Field validation

**Total:** 13 comprehensive tests

## Performance

With wait logic and caching:
- Full test suite: ~30-40 seconds
- Individual framework: ~5-10 seconds
- Single test: ~1-3 seconds

## Future Enhancements

Potential additions:
1. ABS library checking before Hardcover queries
2. Cross-validation between ABS and Hardcover data
3. Bulk import testing
4. Series completion checking
5. Narrator field validation
6. Publisher field extraction
7. ISBN/ASIN matching tests
