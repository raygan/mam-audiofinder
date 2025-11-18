# BACKEND.md - Technical Implementation Details

This document provides detailed technical information about backend services, APIs, and workflows in MAM Audiobook Finder.

---

## Table of Contents

- [Unified Description Service](#unified-description-service)
- [Description Fetching API](#description-fetching-api)
- [Integration Examples](#integration-examples)
- [Caching Strategy](#caching-strategy)
- [Error Handling](#error-handling)

---

## Unified Description Service

The **Unified Description Service** (`description_service.py`) provides a single interface for fetching book descriptions from multiple sources with automatic fallback.

### Architecture

```
User Request
    ↓
┌─────────────────────────────────────┐
│   Description Service               │
│   (description_service.py)          │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│   In-Memory Cache (24hr TTL)        │
│   Key: title|author|asin|isbn       │
└─────────────────────────────────────┘
    ↓ (cache miss)
┌─────────────────────────────────────┐
│   Source 1: Audiobookshelf          │
│   • Searches library by ASIN/ISBN   │
│   • Falls back to title/author      │
│   • Returns description + metadata  │
└─────────────────────────────────────┘
    ↓ (no description or ABS not configured)
┌─────────────────────────────────────┐
│   Source 2: Hardcover API           │
│   • Searches books by title/author  │
│   • Returns description + metadata  │
└─────────────────────────────────────┘
    ↓ (no description found)
┌─────────────────────────────────────┐
│   Return: source='none'             │
│   Description: ""                   │
└─────────────────────────────────────┘
```

### Matching Algorithm

#### ABS Matching (Priority Order)

1. **ASIN Match** (Score: 200 points)
   ```python
   if asin and item_asin and asin.lower() == item_asin:
       score = 200  # Highest confidence
   ```

2. **ISBN Match** (Score: 200 points)
   ```python
   elif isbn and item_isbn and isbn.lower() == item_isbn:
       score = 200
   ```

3. **Title Match** (Score: 50-100 points)
   ```python
   if item_title == title_lower:
       score += 100  # Exact match
   elif title_lower in item_title or item_title in title_lower:
       score += 50   # Partial match
   ```

4. **Author Match** (Score: 25-50 points)
   ```python
   if item_author == author_lower:
       score += 50   # Exact match
   elif author_lower in item_author or item_author in author_lower:
       score += 25   # Partial match
   ```

**Minimum Score:** 50 points required to accept a match

#### Hardcover Matching

Similar scoring system but limited to title/author matching (no ASIN/ISBN support).

### API Methods

#### `get_description()`

Main method for fetching descriptions with fallback logic.

```python
from description_service import description_service

result = await description_service.get_description(
    title="Project Hail Mary",
    author="Andy Weir",
    asin="B08FHBV4ZX",           # Optional
    isbn="9780593135204",         # Optional
    abs_item_id="li_abc123",      # Optional (direct ABS item ID)
    force_refresh=False           # Optional (skip cache)
)
```

**Returns:**
```python
{
    "description": "Ryland Grace is the sole survivor...",
    "source": "hardcover",  # or "abs" or "none"
    "metadata": {
        "book_id": 123456,
        "title": "Project Hail Mary",
        "authors": ["Andy Weir"],
        "series_names": [],
        "published_year": 2021
    },
    "cached": False,
    "fetched_at": "2025-11-18T12:34:56Z"
}
```

#### `clear_cache()`

Clear the in-memory description cache.

```python
description_service.clear_cache()
```

#### `get_cache_stats()`

Get cache statistics.

```python
stats = description_service.get_cache_stats()
# Returns: {"total_entries": 42, "valid_entries": 38, "cache_ttl": 86400, "fallback_enabled": true}
```

---

## Description Fetching API

### Endpoints

#### POST /api/description/fetch

Fetch book description from available sources with fallback.

**Request:**
```json
{
    "title": "The Way of Kings",
    "author": "Brandon Sanderson",
    "asin": "B003P2WO5E",
    "isbn": "9780765365279",
    "abs_item_id": "li_abc123",
    "force_refresh": false
}
```

**Response:**
```json
{
    "description": "I long for the days before the Last Desolation...",
    "source": "abs",
    "metadata": {
        "title": "The Way of Kings",
        "authorName": "Brandon Sanderson",
        "narratorName": "Michael Kramer, Kate Reading",
        "series": [{"name": "The Stormlight Archive", "sequence": "1"}],
        "duration": 45900.5,
        "asin": "B003P2WO5E"
    },
    "cached": false,
    "fetched_at": "2025-11-18T10:30:00Z"
}
```

**Error Response:**
```json
{
    "detail": "Description fetch failed: Connection timeout"
}
```

**Status Codes:**
- `200` - Success (description found or not found)
- `400` - Bad request (missing title)
- `500` - Server error (API failure, exception)
- `503` - Service unavailable (ABS/Hardcover not configured)

#### GET /api/description/stats

Get cache statistics.

**Response:**
```json
{
    "total_entries": 42,
    "valid_entries": 38,
    "cache_ttl": 86400,
    "fallback_enabled": true
}
```

#### POST /api/description/cache/clear

Clear the description cache.

**Response:**
```json
{
    "success": true,
    "message": "Description cache cleared"
}
```

---

## Integration Examples

### Example 1: Basic Description Fetch

```python
from description_service import description_service

async def fetch_book_description(title: str, author: str):
    """Fetch description for a book."""
    result = await description_service.get_description(
        title=title,
        author=author
    )

    if result["source"] == "none":
        print(f"No description found for '{title}'")
        return None

    print(f"Description from {result['source']}: {result['description'][:100]}...")
    return result
```

### Example 2: Post-Import Description Update

```python
async def update_description_after_import(
    item_id: str,
    title: str,
    author: str,
    asin: str = "",
    isbn: str = ""
):
    """Update database with description after import."""

    # Fetch description using unified service
    result = await description_service.get_description(
        title=title,
        author=author,
        asin=asin,
        isbn=isbn,
        abs_item_id=item_id
    )

    if result["description"]:
        # Update history table
        from db import engine
        from sqlalchemy import text

        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE history
                SET abs_description = :description,
                    abs_metadata = :metadata,
                    abs_description_source = :source
                WHERE abs_item_id = :item_id
            """), {
                "description": result["description"],
                "metadata": json.dumps(result["metadata"]),
                "source": result["source"],
                "item_id": item_id
            })
```

### Example 3: Frontend API Call

```javascript
// Fetch description via API
async function fetchDescription(title, author) {
    const response = await fetch('/api/description/fetch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            title: title,
            author: author,
            force_refresh: false
        })
    });

    if (!response.ok) {
        console.error('Failed to fetch description');
        return null;
    }

    const data = await response.json();

    if (data.source === 'none') {
        console.log('No description available');
        return null;
    }

    console.log(`Description from ${data.source}:`, data.description);
    return data;
}
```

### Example 4: Using Direct ABS Item ID

```python
async def get_description_by_abs_id(abs_item_id: str):
    """Fetch description using direct ABS item ID (fastest method)."""
    result = await description_service.get_description(
        title="",  # Not needed when abs_item_id is provided
        author="",
        abs_item_id=abs_item_id
    )

    return result["description"]
```

---

## Caching Strategy

### Cache Keys

Cache keys are generated based on available identifiers (priority order):

1. **ABS Item ID:** `desc:abs:{item_id}`
2. **ASIN:** `desc:asin:{asin.lower()}`
3. **ISBN:** `desc:isbn:{isbn.lower()}`
4. **Title + Author:** `desc:title:{title.lower()}|{author.lower()}`

### Cache TTL

- **Default:** 86400 seconds (24 hours)
- **Configurable:** Set `DESCRIPTION_CACHE_TTL` env var
- **Cache Type:** In-memory (not persistent across restarts)

### Cache Invalidation

**Manual:**
```python
description_service.clear_cache()
```

**Automatic:**
- Entries expire after TTL
- Force refresh: `force_refresh=True`
- Container restart clears cache

### Performance Considerations

**Cache Hit:**
- Response time: <1ms
- No API calls made
- No network overhead

**Cache Miss:**
- ABS query: ~100-500ms (depends on library size)
- Hardcover query: ~200-800ms (depends on API load)
- Total with fallback: ~1-2 seconds max

---

## Error Handling

### Exception Handling

The service gracefully handles all exceptions:

```python
try:
    result = await description_service.get_description(title, author)
except Exception as e:
    # Service never raises - always returns a result
    # But you can catch errors from the calling code
    logger.error(f"Unexpected error: {e}")
```

### Error Scenarios

| Scenario | Behavior | Response |
|----------|----------|----------|
| **Empty title** | Skip API calls | `source: "none"` |
| **ABS not configured** | Skip ABS, try Hardcover | `source: "hardcover"` or `"none"` |
| **Hardcover not configured** | Try ABS only | `source: "abs"` or `"none"` |
| **ABS timeout** | Log error, try Hardcover | `source: "hardcover"` or `"none"` |
| **Hardcover timeout** | Log error, return none | `source: "none"` |
| **Network error** | Log error, try next source | Fallback chain continues |
| **No match found** | Search all sources | `source: "none"`, `description: ""` |

### Logging

All operations are logged with appropriate levels:

```python
# Info - successful operations
logger.info(f"✅ Got description from ABS for '{title}' (487 chars)")

# Warning - non-critical issues
logger.warning(f"⚠️  No title provided for description fetch")

# Error - failures (non-blocking)
logger.error(f"❌ ABS description fetch failed: Connection timeout")

# Debug - detailed diagnostics
logger.debug(f"📦 Using cached metadata for item {item_id}")
```

---

## Configuration

### Environment Variables

```bash
# Enable/disable Hardcover fallback
DESCRIPTION_FALLBACK_ENABLED=true        # Default: true

# Cache duration in seconds (24 hours)
DESCRIPTION_CACHE_TTL=86400              # Default: 86400

# Required for ABS integration
ABS_BASE_URL=http://audiobookshelf:13378
ABS_API_KEY=your_abs_api_key

# Required for Hardcover integration
HARDCOVER_API_TOKEN=your_hardcover_token
```

### Feature Flags

**Disable Hardcover Fallback:**
```bash
DESCRIPTION_FALLBACK_ENABLED=false
```

Result: Only ABS will be queried, no Hardcover fallback.

**Shorter Cache TTL:**
```bash
DESCRIPTION_CACHE_TTL=3600  # 1 hour
```

Result: Descriptions refresh more frequently (more API calls).

---

## Testing

### Unit Tests

Run the comprehensive test suite:

```bash
# All description service tests
pytest tests/test_description_service.py -v

# Specific test class
pytest tests/test_description_service.py::TestDescriptionServiceFallback -v

# Single test
pytest tests/test_description_service.py::TestDescriptionServiceCaching::test_cache_hit -v
```

### Live Demo

Test with real API calls:

```bash
# Run interactive demo
python /app/demo_description_fetch.py
```

The demo shows:
- Real descriptions from ABS
- Real descriptions from Hardcover
- Fallback logic in action
- Caching behavior
- ASIN/ISBN matching

### Manual API Testing

```bash
# Test description fetch
curl -X POST http://localhost:8008/api/description/fetch \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Project Hail Mary",
    "author": "Andy Weir",
    "force_refresh": true
  }'

# Get cache stats
curl http://localhost:8008/api/description/stats

# Clear cache
curl -X POST http://localhost:8008/api/description/cache/clear
```

---

## Database Integration

### Migration 011: Description Source Tracking

```sql
-- Add description_source column to covers table
ALTER TABLE covers ADD COLUMN description_source TEXT;

-- Update existing rows
UPDATE covers
SET description_source = 'abs'
WHERE abs_description IS NOT NULL AND abs_description != '';
```

### Query Examples

**Get all descriptions from Hardcover:**
```sql
SELECT title, author, abs_description, description_source
FROM covers
WHERE description_source = 'hardcover';
```

**Get books without descriptions:**
```sql
SELECT title, author
FROM covers
WHERE abs_description IS NULL OR abs_description = '';
```

**Count descriptions by source:**
```sql
SELECT description_source, COUNT(*) as count
FROM covers
WHERE abs_description IS NOT NULL
GROUP BY description_source;
```

---

## Troubleshooting

### Issue: "No description found" for books in ABS

**Possible causes:**
1. Book title doesn't match exactly
2. ASIN/ISBN not in metadata
3. ABS_LIBRARY_ID not set correctly

**Debug steps:**
```python
# Enable debug logging
import logging
logging.getLogger("mam-audiofinder").setLevel(logging.DEBUG)

# Check what ABS returns
result = await description_service.get_description(
    title="Your Book Title",
    author="Author Name",
    force_refresh=True
)
```

### Issue: Hardcover fallback not working

**Check configuration:**
```bash
# Verify token is set
echo $HARDCOVER_API_TOKEN

# Verify fallback is enabled
echo $DESCRIPTION_FALLBACK_ENABLED
```

### Issue: Slow response times

**Optimize:**
1. Ensure cache is working (check `cached: true` in response)
2. Reduce ABS library size scanning
3. Check network latency to ABS/Hardcover
4. Consider increasing `DESCRIPTION_CACHE_TTL`

### Issue: Cache not clearing

**Force clear:**
```bash
# Via API
curl -X POST http://localhost:8008/api/description/cache/clear

# Via container restart
docker compose restart mam-audiofinder
```

---

## Performance Metrics

### Typical Response Times

| Scenario | Time | API Calls |
|----------|------|-----------|
| Cache hit | <1ms | 0 |
| ABS hit (fresh) | 100-500ms | 1-2 |
| Hardcover fallback | 200-800ms | 2-3 |
| Both fail | 1-2s | 3-4 |

### Cache Hit Rates

Typical hit rates after warm-up:
- **First hour:** ~20-30% (cold cache)
- **After 24 hours:** ~70-80% (warm cache)
- **Steady state:** ~85-95% (hot cache)

### Resource Usage

- **Memory:** ~10-50KB per cached description
- **Network:** 1-5KB per API request
- **CPU:** Negligible (<1% during fetch)

---

## Future Enhancements

Potential improvements to the description service:

1. **Persistent cache** - SQLite storage for cache survival across restarts
2. **Additional sources** - Google Books, Goodreads, OpenLibrary
3. **Async batch fetching** - Fetch multiple descriptions in parallel
4. **Smart cache warming** - Pre-fetch descriptions for popular books
5. **Fuzzy title matching** - Levenshtein distance for better matching
6. **Description quality scoring** - Prefer longer, more detailed descriptions
7. **Multi-language support** - Fetch descriptions in user's language

---

## References

- **Source Code:** `app/description_service.py` (~330 lines)
- **API Routes:** `app/routes/description_route.py` (~120 lines)
- **Tests:** `app/tests/test_description_service.py` (~450 lines, 30+ tests)
- **Demo:** `app/demo_description_fetch.py` (~270 lines)
- **Hardcover Client:** `app/hardcover_client.py` (search_book_by_title method)
- **ABS Client:** `app/abs_client.py` (fetch_item_details method)
