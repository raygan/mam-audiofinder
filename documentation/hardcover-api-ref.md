# Hardcover API Reference

**⚠️ IMPORTANT:** The Hardcover API is a **GraphQL API**, not a REST API. All queries are made via GraphQL to a single endpoint.

**Official Documentation:** https://docs.hardcover.app/api/getting-started/
**API Endpoint:** `https://api.hardcover.app/v1/graphql`
**API Status:** Beta (actively being developed)

This document summarizes the Hardcover GraphQL API's capabilities, authentication, and usage patterns.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Rate Limits](#rate-limits)
3. [GraphQL Endpoint](#graphql-endpoint)
4. [Search Queries](#search-queries)
5. [Content Types](#content-types)
6. [Series Queries](#series-queries)

---

## Authentication

### Getting Your API Token

1. Log in to your Hardcover account
2. Navigate to your account settings page
3. Click on the **Hardcover API** link
4. Your API token will be displayed at the top of the page

### Using Your Token

**⚠️ Security Warning:** API tokens must be kept private and should **only** be used from backend code, never in browser/client-side code.

**Authentication Header:**
```
Authorization: Bearer YOUR_API_TOKEN
```

**Example with httpx (Python):**
```python
headers = {"Authorization": f"Bearer {your_api_token}"}
response = await client.post(
    "https://api.hardcover.app/v1/graphql",
    headers=headers,
    json={"query": your_graphql_query}
)
```

---

## Rate Limits

| Limit Type | Value |
|------------|-------|
| **Requests per minute** | 60 |
| **Query timeout** | 30 seconds max |

**Important:** The same API used by the Hardcover website, iOS, and Android apps is available to developers. Rate limits apply per API token.

**Recommendation:** Implement caching and request batching to stay within limits. Consider 5-minute cache TTL for frequently accessed data.

### Throttle & Retry Strategy

**Implementation Requirements for MAM AudioFinder:**

1. **Request Rate Limiting**
   - Track requests per minute in memory (simple counter with timestamp)
   - If approaching 60 req/min, sleep until next minute window
   - Add small random jitter (50-200ms) to avoid thundering herd

2. **Caching Strategy**
   - Cache series searches for 5 minutes (300 seconds TTL)
   - Cache series book lists for 5 minutes
   - Store in SQLite table `series_cache` (Migration 009)
   - Cache key format: `search:{query_hash}` or `series:{series_id}`

3. **Retry Policy (429 Rate Limit Errors)**
   - Max retries: 3
   - Exponential backoff: 2s, 4s, 8s
   - Add random jitter: 0-1s to spread retry load
   - Log all rate limit hits for monitoring

4. **Timeout Handling**
   - Set httpx timeout to 25s (below API's 30s max)
   - Treat timeouts as retriable errors (same backoff policy)
   - Max timeout retries: 2

5. **Circuit Breaker (Optional Enhancement)**
   - After 5 consecutive failures, pause Hardcover requests for 60s
   - Return cached data during circuit breaker period
   - Log circuit breaker events

**Example Python Implementation:**
```python
import time
import asyncio
from datetime import datetime, timedelta

class HardcoverRateLimiter:
    def __init__(self, requests_per_minute=60):
        self.rpm = requests_per_minute
        self.requests = []  # List of request timestamps

    async def acquire(self):
        """Wait if necessary to stay within rate limit"""
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)

        # Remove requests older than 1 minute
        self.requests = [ts for ts in self.requests if ts > cutoff]

        if len(self.requests) >= self.rpm:
            # Calculate sleep time
            oldest = self.requests[0]
            sleep_until = oldest + timedelta(minutes=1)
            sleep_seconds = (sleep_until - now).total_seconds()

            if sleep_seconds > 0:
                await asyncio.sleep(sleep_seconds + random.uniform(0.05, 0.2))

        self.requests.append(datetime.now())
```

**Error Response Codes:**
- `429 Too Many Requests` - Rate limit exceeded, implement backoff
- `408 Request Timeout` - Query took >30s, retry with simpler query
- `500/502/503` - Server error, retry with backoff

---

## GraphQL Endpoint

**URL:** `https://api.hardcover.app/v1/graphql`
**Method:** `POST`
**Content-Type:** `application/json`

### Request Format

```json
{
  "query": "your GraphQL query string",
  "variables": {
    "optional": "variables"
  }
}
```

### Testing Queries

Hardcover provides a **GraphQL Console** for testing queries:
- Add a header called `authorization` with your token as the value
- Write and test queries interactively

---

## Search Queries

The Hardcover API supports searching across multiple content types using GraphQL queries.

### Searchable Content Types

- `books`
- `authors`
- `series`
- `lists` (user-created)
- `users`
- `characters`
- `publishers`
- `prompts`

### Example: Basic Book Search

```graphql
query SearchBooks($query: String!) {
  books(where: {title: {_ilike: $query}}, limit: 25) {
    id
    title
    subtitle
    pages
    published_year
    image
    authors {
      id
      name
    }
  }
}
```

**Variables:**
```json
{
  "query": "%Sanderson%"
}
```

### Filtering with `where` Clause

GraphQL queries support filtering with the `where` clause. Example:

```graphql
{
  me {
    user_books(where: {status_id: {_eq: 3}}) {
      book {
        title
        authors {
          name
        }
      }
    }
  }
}
```

**Common Operators:**
- `_eq` - equals
- `_ilike` - case-insensitive LIKE
- `_gt` / `_lt` - greater than / less than
- `_in` - in array

---

## Content Types

### Books

**Searchable Fields:** `title`, `subtitle`, `series`, `author_names`, `description`

**Available Fields:**
- `id` - Unique identifier
- `title` - Book title
- `subtitle` - Book subtitle
- `description` - Book synopsis/description
- `pages` - Page count
- `published_year` - Year of publication
- `image` - Cover image URL
- `goodreads_id` - Goodreads identifier
- `authors` - Array of author objects
  - `id` - Author ID
  - `name` - Author name
- `series` - Series information (if part of series)
- **Note:** Additional fields may be available; refer to GraphQL introspection

### Authors

**Searchable Fields:** `name`, `name_personal`, `alternate_names`, `series_names`, `books`

**Available Fields:**
- `id` - Unique identifier
- `name` - Author name
- `name_personal` - Personal name variant
- `alternate_names` - Alternative name spellings
- `goodreads_id` - Goodreads identifier
- `slug` - URL-friendly identifier
- `image` - Author photo URL
- `books_count` - Total number of books

### Series

**Searchable Fields:** `name`, `author_name`

**Available Fields:**
- `id` - Unique identifier
- `name` - Series name
- `author_name` - Primary author's name
- `primary_books_count` - Count of books with integer positions (1, 2, 3, etc.; excludes 1.5 or empty)
- `readers_count` - Sum of `users_read_count` for all books in series
- **Note:** Query books within a series using series relationships

### Lists

**Searchable Fields:** `name`, `user_name`, `description`

**Available Fields:**
- `id` - Unique identifier
- `name` - List name
- `user_id` - Creator's user ID
- `slug` - URL-friendly identifier
- `description` - List description
- `entries_count` - Number of items in list

### Users

**Searchable Fields:** `name`, `username`

**Available Fields:**
- `id` - Unique identifier
- `name` - Display name
- `username` - Username
- `image` - Profile image URL

### Other Types

The following types are supported but require further documentation:
- `character`
- `publisher`
- `prompt`

---

## Series Queries

**Critical for MAM AudioFinder Phase 2 Integration**

### Example: Search for Series by Name

```graphql
query SearchSeries($name: String!) {
  series(where: {name: {_ilike: $name}}, limit: 10) {
    id
    name
    author_name
    primary_books_count
    readers_count
  }
}
```

**Variables:**
```json
{
  "name": "%Stormlight%"
}
```

### Example: Get Books in a Series

```graphql
query GetSeriesBooks($seriesId: Int!) {
  series_by_pk(id: $seriesId) {
    id
    name
    books(order_by: {position: asc}) {
      id
      title
      position
      published_year
      image
      authors {
        id
        name
      }
    }
  }
}
```

**Variables:**
```json
{
  "seriesId": 12345
}
```

**Note:** The exact field names and query structure may vary. Test queries in the GraphQL console to confirm.
