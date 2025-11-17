"""
Hardcover API client for MAM Audiobook Finder.
Handles GraphQL API communication with Hardcover for series discovery.
"""
import logging
import httpx
import json
import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import text

from config import (
    HARDCOVER_API_TOKEN,
    HARDCOVER_BASE_URL,
    HARDCOVER_CACHE_TTL,
    HARDCOVER_RATE_LIMIT
)
from db.db import get_db_engine

logger = logging.getLogger("mam-audiofinder")


class HardcoverRateLimiter:
    """Rate limiter for Hardcover API (60 requests per minute)."""

    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.requests: List[datetime] = []
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait if necessary to stay within rate limit."""
        async with self._lock:
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
                    # Add random jitter to avoid thundering herd
                    import random
                    jitter = random.uniform(0.05, 0.2)
                    await asyncio.sleep(sleep_seconds + jitter)
                    logger.info(f"⏱️  Rate limit: slept {sleep_seconds + jitter:.2f}s")

            self.requests.append(datetime.now())


class HardcoverClient:
    """Client for interacting with Hardcover GraphQL API."""

    # Shared HTTP client for connection pooling
    _shared_client: Optional[httpx.AsyncClient] = None
    _rate_limiter: Optional[HardcoverRateLimiter] = None
    # Request counting (class-level for all instances)
    _request_count: int = 0
    _cache_hit_count: int = 0

    def __init__(self):
        """Initialize Hardcover client."""
        self.base_url = HARDCOVER_BASE_URL
        self.api_token = HARDCOVER_API_TOKEN
        self.cache_ttl = HARDCOVER_CACHE_TTL

        # Initialize shared client if not already done
        if HardcoverClient._shared_client is None:
            HardcoverClient._shared_client = httpx.AsyncClient(
                timeout=25.0,  # Below API's 30s max
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
            )
            logger.info("🔧 Initialized shared HTTP client for Hardcover requests")

        # Initialize rate limiter
        if HardcoverClient._rate_limiter is None:
            HardcoverClient._rate_limiter = HardcoverRateLimiter(HARDCOVER_RATE_LIMIT)
            logger.info(f"🔧 Initialized Hardcover rate limiter ({HARDCOVER_RATE_LIMIT} req/min)")

    @property
    def is_configured(self) -> bool:
        """Check if Hardcover API is configured."""
        return bool(self.api_token)

    @classmethod
    def get_request_count(cls) -> int:
        """Get total number of API requests made."""
        return cls._request_count

    @classmethod
    def get_cache_hit_count(cls) -> int:
        """Get total number of cache hits."""
        return cls._cache_hit_count

    @classmethod
    def reset_counters(cls):
        """Reset request and cache counters (useful for testing)."""
        cls._request_count = 0
        cls._cache_hit_count = 0
        logger.info("🔄 Reset Hardcover API counters")

    async def _execute_graphql(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a GraphQL query with rate limiting and retry logic.

        Args:
            query: GraphQL query string
            variables: Query variables
            max_retries: Maximum number of retries on failure

        Returns:
            GraphQL response data or None on failure
        """
        if not self.is_configured:
            logger.warning("⚠️  Hardcover API not configured (missing HARDCOVER_API_TOKEN)")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                # Acquire rate limit token
                await self._rate_limiter.acquire()

                # Increment request counter
                HardcoverClient._request_count += 1

                # Execute request
                response = await self._shared_client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )

                # Log response for debugging (only in non-200 cases or at debug level)
                if response.status_code != 200:
                    logger.debug(f"🔍 Response status: {response.status_code}")
                    logger.debug(f"🔍 Response headers: {dict(response.headers)}")
                    logger.debug(f"🔍 Response body: {response.text[:500]}")

                # Handle rate limiting (429)
                if response.status_code == 429:
                    # Exponential backoff: 2s, 4s, 8s
                    import random
                    backoff = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"⏱️  Rate limited (429), backing off {backoff:.1f}s...")
                    await asyncio.sleep(backoff)
                    continue

                # Handle other HTTP errors
                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"❌ Hardcover API error: {last_error}")

                    # Retry on 5xx errors
                    if response.status_code >= 500 and attempt < max_retries:
                        import random
                        backoff = (2 ** attempt) + random.uniform(0, 1)
                        logger.info(f"🔄 Retrying after {backoff:.1f}s...")
                        await asyncio.sleep(backoff)
                        continue
                    return None

                # Parse response
                data = response.json()

                # Check for GraphQL errors
                if "errors" in data:
                    logger.error(f"❌ GraphQL errors: {data['errors']}")
                    return None

                # Log successful response structure at debug level
                result_data = data.get("data")
                if result_data:
                    logger.debug(f"✅ GraphQL response keys: {list(result_data.keys())}")

                return result_data

            except httpx.TimeoutException as e:
                last_error = f"Timeout: {e}"
                logger.warning(f"⏱️  Hardcover request timeout (attempt {attempt + 1}/{max_retries + 1})")
                if attempt < max_retries:
                    import random
                    await asyncio.sleep((2 ** attempt) + random.uniform(0, 1))
                    continue

            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                logger.error(f"❌ Hardcover request failed: {last_error}")
                if attempt < max_retries:
                    import random
                    await asyncio.sleep((2 ** attempt) + random.uniform(0, 1))
                    continue

        logger.error(f"❌ All {max_retries + 1} attempts failed: {last_error}")
        return None

    def _get_cache_key(self, cache_type: str, identifier: str) -> str:
        """Generate cache key for a query."""
        # Hash identifier for consistent key length
        hash_value = hashlib.md5(identifier.encode()).hexdigest()[:12]
        return f"{cache_type}:{hash_value}"

    async def _get_cached(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached data if not expired."""
        try:
            engine = get_db_engine()
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT response_data, expires_at, hit_count
                        FROM series_cache
                        WHERE cache_key = :key
                        AND datetime(expires_at) > datetime('now')
                    """),
                    {"key": cache_key}
                ).fetchone()

                if result:
                    # Update hit count
                    conn.execute(
                        text("UPDATE series_cache SET hit_count = hit_count + 1 WHERE cache_key = :key"),
                        {"key": cache_key}
                    )
                    conn.commit()

                    # Increment class-level cache hit counter
                    HardcoverClient._cache_hit_count += 1

                    logger.info(f"✅ Cache HIT for {cache_key} (hits: {result[2] + 1})")
                    return json.loads(result[0])

                logger.info(f"❌ Cache MISS for {cache_key}")
                return None

        except Exception as e:
            logger.error(f"❌ Cache retrieval error: {e}")
            return None

    async def _set_cache(
        self,
        cache_key: str,
        cache_type: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store data in cache with TTL."""
        try:
            engine = get_db_engine()
            expires_at = datetime.now() + timedelta(seconds=self.cache_ttl)

            with engine.connect() as conn:
                # Build metadata fields
                meta_fields = metadata or {}

                conn.execute(
                    text("""
                        INSERT OR REPLACE INTO series_cache
                        (cache_key, cache_type, response_data, expires_at,
                         query_title, query_author, query_normalized,
                         series_id, series_name, series_author)
                        VALUES
                        (:key, :type, :data, :expires,
                         :title, :author, :normalized,
                         :series_id, :series_name, :series_author)
                    """),
                    {
                        "key": cache_key,
                        "type": cache_type,
                        "data": json.dumps(data),
                        "expires": expires_at.isoformat(),
                        "title": meta_fields.get("title"),
                        "author": meta_fields.get("author"),
                        "normalized": meta_fields.get("normalized"),
                        "series_id": meta_fields.get("series_id"),
                        "series_name": meta_fields.get("series_name"),
                        "series_author": meta_fields.get("series_author"),
                    }
                )
                conn.commit()

                logger.info(f"💾 Cached {cache_key} (TTL: {self.cache_ttl}s)")

        except Exception as e:
            logger.error(f"❌ Cache storage error: {e}")

    async def search_series(
        self,
        title: str,
        author: str = "",
        limit: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Search for series by title and/or author.

        Args:
            title: Series name to search for
            author: Author name (optional)
            limit: Maximum number of results (default: 10)

        Returns:
            List of series dictionaries with keys:
            - series_id: Hardcover series ID
            - series_name: Series name
            - author_name: Primary author
            - book_count: Number of books
            - readers_count: Total readers
            - books: List of book titles (strings, up to 5 books from search results)
            Returns None if API call fails, empty list [] if no results found.
        """
        if not self.is_configured:
            return None

        # Generate cache key
        cache_key = self._get_cache_key("search", f"{title}|{author}|limit{limit}")

        # Check cache
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached.get("series", [])

        # Build GraphQL query using Hardcover's search function
        query = """
        query SearchSeries($query: String!, $queryType: String!, $perPage: Int!) {
          search(query: $query, query_type: $queryType, per_page: $perPage) {
            results
          }
        }
        """

        variables = {
            "query": title,
            "queryType": "Series",
            "perPage": limit
        }

        logger.info(f"🔍 Searching Hardcover for series: '{title}' (author: '{author}', limit: {limit})")

        # Execute query
        data = await self._execute_graphql(query, variables)

        if data is None:
            # API call failed
            return None

        if "search" not in data:
            logger.warning(f"⚠️  No search results in response for '{title}'")
            return []

        search_data = data["search"]

        # Log the search response structure for debugging
        logger.debug(f"🔍 Search response keys: {list(search_data.keys())}")

        # According to API docs, response structure is:
        # { "search": { "results": { "found": N, "hits": [...] } } }
        results = search_data.get("results")

        if results is None:
            logger.warning(f"⚠️  No results field in search response for '{title}'")
            return []

        # Handle string response (legacy/unexpected format)
        if isinstance(results, str):
            import json
            try:
                results = json.loads(results)
                logger.debug("📝 Parsed results from JSON string (legacy format)")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse results JSON: {e}")
                return []

        # Expected format: results is a dict with 'found' and 'hits' keys
        if isinstance(results, dict):
            found_count = results.get("found", 0)
            hits = results.get("hits", [])

            logger.debug(f"🔍 Results structure: found={found_count}, hits={len(hits)}")

            if not hits:
                logger.info(f"ℹ️  No series found matching '{title}' (found={found_count})")
                return []

            # Process hits array
            series_list = []
            for idx, hit in enumerate(hits):
                # Each hit has a 'document' field containing the actual data
                doc = hit.get("document", {})

                # Log first item structure for debugging
                if idx == 0:
                    logger.debug(f"🔍 First hit keys: {list(hit.keys())}")
                    logger.debug(f"🔍 First document keys: {list(doc.keys()) if isinstance(doc, dict) else 'Not a dict'}")

                # Extract series fields including books array
                books = doc.get("books", [])
                # Ensure books is a list (may be strings or empty)
                if not isinstance(books, list):
                    books = []

                series_list.append({
                    "series_id": doc.get("id"),
                    "series_name": doc.get("name", ""),
                    "author_name": doc.get("author_name", ""),
                    "book_count": doc.get("primary_books_count", doc.get("books_count", doc.get("book_count", 0))),
                    "readers_count": doc.get("readers_count", 0),
                    "books": books  # Array of book title strings (up to 5)
                })

        # Fallback: if results is already a list (old/unexpected format)
        elif isinstance(results, list):
            logger.debug(f"🔍 Results is a list (unexpected format), processing {len(results)} items")

            if len(results) == 0:
                logger.info(f"ℹ️  No series found matching '{title}'")
                return []

            series_list = []
            for idx, item in enumerate(results):
                # Typesense may wrap the actual document in a 'document' field
                doc = item.get("document", item) if isinstance(item, dict) else item

                # Log first item structure for debugging
                if idx == 0:
                    logger.debug(f"🔍 First result keys: {list(doc.keys()) if isinstance(doc, dict) else 'Not a dict'}")

                # Extract fields with defensive fallbacks including books array
                books = doc.get("books", [])
                if not isinstance(books, list):
                    books = []

                series_list.append({
                    "series_id": doc.get("id"),
                    "series_name": doc.get("name", ""),
                    "author_name": doc.get("author_name", ""),
                    "book_count": doc.get("primary_books_count", doc.get("books_count", doc.get("book_count", 0))),
                    "readers_count": doc.get("readers_count", 0),
                    "books": books  # Array of book title strings (up to 5)
                })

        else:
            logger.error(f"❌ Unexpected results type: {type(results)}")
            return []

        logger.info(f"✅ Found {len(series_list)} series matches")

        # Cache results
        await self._set_cache(
            cache_key,
            "search",
            {"series": series_list},
            {"title": title, "author": author, "normalized": title.lower()}
        )

        return series_list

    async def list_series_books(self, series_id: int) -> Optional[Dict[str, Any]]:
        """
        List books in a series using the documented search endpoint.

        NOTE: This function now uses only the documented Hardcover search API.
        Book information is limited to titles only (up to 5 books).

        Strategy:
        1. First, get series basic info (id, name, author) using series_by_pk
        2. Then search for the series by name to get books array
        3. Return combined results

        Args:
            series_id: Hardcover series ID

        Returns:
            Dictionary with keys:
            - series_id: Hardcover series ID
            - series_name: Series name
            - author_name: Primary author
            - books: List of book titles (strings, limited to top 5 from search)
            Returns None if series not found or API fails.
        """
        if not self.is_configured:
            return None

        # Generate cache key
        cache_key = self._get_cache_key("series", str(series_id))

        # Check cache
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        # Step 1: Get series basic info (without books field which doesn't exist)
        query = """
        query GetSeriesInfo($seriesId: Int!) {
          series_by_pk(id: $seriesId) {
            id
            name
            author {
              id
              name
            }
          }
        }
        """

        variables = {"seriesId": series_id}

        logger.info(f"📚 Fetching series info for ID {series_id}")

        data = await self._execute_graphql(query, variables)

        if not data or "series_by_pk" not in data or not data["series_by_pk"]:
            logger.warning(f"⚠️  Series {series_id} not found")
            return None

        series_data = data["series_by_pk"]
        series_name = series_data["name"]
        author_obj = series_data.get("author", {})
        author_name = author_obj.get("name", "") if author_obj else ""

        logger.info(f"✅ Found series: '{series_name}' by {author_name}")

        # Step 2: Search for this series to get books array
        logger.info(f"🔍 Searching for books in series '{series_name}'")
        search_results = await self.search_series(title=series_name, limit=1)

        books = []
        if search_results and len(search_results) > 0:
            # Use the first result (should be exact match)
            first_result = search_results[0]
            if first_result.get("series_id") == str(series_id) or first_result.get("series_id") == series_id:
                books = first_result.get("books", [])
                logger.info(f"✅ Found {len(books)} books from search results")
            else:
                logger.warning(f"⚠️  Search result mismatch: got ID {first_result.get('series_id')}, expected {series_id}")
                # Still use the books but log the discrepancy
                books = first_result.get("books", [])

        result = {
            "series_id": series_data["id"],
            "series_name": series_name,
            "author_name": author_name,
            "books": books  # Array of book title strings (up to 5)
        }

        logger.info(f"✅ Returning {len(books)} book titles for series '{series_name}'")

        # Cache results
        await self._set_cache(
            cache_key,
            "books",
            result,
            {
                "series_id": series_id,
                "series_name": series_name,
                "series_author": author_name
            }
        )

        return result

    async def search_books_by_author(
        self,
        author_name: str,
        limit: int = 10,
        fields: Optional[List[str]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Search for books by a specific author using GraphQL query.

        Args:
            author_name: Author name to search for
            limit: Maximum number of results
            fields: List of fields to retrieve (default: title, description, series_names)

        Returns:
            List of book dictionaries with requested fields, or None on failure
        """
        if not self.is_configured:
            return None

        # Generate cache key
        fields_key = ",".join(sorted(fields)) if fields else "default"
        cache_key = self._get_cache_key("books_by_author", f"{author_name}|{limit}|{fields_key}")

        # Check cache
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached.get("books", [])

        # Default fields if not specified
        if fields is None:
            fields = ["title", "description", "series_names"]

        # Build field selection string
        field_str = "\n            ".join(fields)

        # Build GraphQL query
        query = f"""
        query BooksByAuthor($authorName: String!, $limit: Int!) {{
            books(
                where: {{
                    contributions: {{
                        author: {{
                            name: {{_eq: $authorName}}
                        }}
                    }}
                }}
                limit: $limit
                order_by: {{users_count: desc}}
            ) {{
                id
                {field_str}
            }}
        }}
        """

        variables = {
            "authorName": author_name,
            "limit": limit
        }

        logger.info(f"🔍 Searching Hardcover for books by author: '{author_name}' (limit: {limit})")

        # Execute query
        data = await self._execute_graphql(query, variables)

        if data is None:
            return None

        if "books" not in data:
            logger.warning(f"⚠️  No books field in response for author '{author_name}'")
            return []

        books = data["books"]
        logger.info(f"✅ Found {len(books)} books by {author_name}")

        # Cache results
        await self._set_cache(
            cache_key,
            "books_by_author",
            {"books": books},
            {"author": author_name, "limit": limit}
        )

        return books

    async def get_series_by_author(
        self,
        author_name: str,
        limit: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get series by author name with comprehensive field extraction.

        This method searches for series and attempts to extract:
        - series_names
        - book_series relationships
        - description
        - list_books

        Args:
            author_name: Author name to search for
            limit: Maximum number of results

        Returns:
            List of series dictionaries with comprehensive data
        """
        if not self.is_configured:
            return None

        # Use search_series with author filter
        logger.info(f"🔍 Getting series by author: '{author_name}'")
        results = await self.search_series(title="", author=author_name, limit=limit)

        if results is None:
            return None

        # Filter results to only those matching the author
        if author_name:
            filtered = [s for s in results if author_name.lower() in s.get('author_name', '').lower()]
            logger.info(f"✅ Found {len(filtered)} series by {author_name} (from {len(results)} results)")
            return filtered

        return results


# Global instance
hardcover_client = HardcoverClient()
