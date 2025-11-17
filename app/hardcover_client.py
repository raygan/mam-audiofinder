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
            limit: Maximum number of results

        Returns:
            List of series dictionaries with keys:
            - series_id: Hardcover series ID
            - series_name: Series name
            - author_name: Primary author
            - book_count: Number of books
            - readers_count: Total readers
            Returns None if API call fails, empty list [] if no results found.
        """
        if not self.is_configured:
            return None

        # Generate cache key
        cache_key = self._get_cache_key("search", f"{title}|{author}")

        # Check cache
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached.get("series", [])

        # Build GraphQL query using Hardcover's search function
        query = """
        query SearchSeries($query: String!, $queryType: String!, $perPage: Int!, $page: Int!) {
          search(query: $query, query_type: $queryType, per_page: $perPage, page: $page) {
            results
          }
        }
        """

        variables = {
            "query": title,
            "queryType": "Series",
            "perPage": limit,
            "page": 1
        }

        logger.info(f"🔍 Searching Hardcover for series: '{title}' (author: '{author}')")

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

        # According to API docs, response contains: ids, results, query, query_type, page, per_page
        results = search_data.get("results")
        logger.debug(f"🔍 Results type: {type(results)}, length: {len(results) if isinstance(results, (list, str)) else 'N/A'}")

        if results is None:
            logger.warning(f"⚠️  No results field in search response for '{title}'")
            return []

        # Results should be an array of Typesense objects
        # If it's a string (legacy behavior), parse it
        if isinstance(results, str):
            import json
            try:
                results = json.loads(results)
                logger.debug("📝 Parsed results from JSON string (legacy format)")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse results JSON: {e}")
                return []

        # Ensure results is a list
        if not isinstance(results, list):
            logger.warning(f"⚠️  Unexpected results format: {type(results)}")
            return []

        if len(results) == 0:
            logger.info(f"ℹ️  No series found matching '{title}'")
            return []

        # Transform results - handle various possible field structures from Typesense
        series_list = []
        for idx, item in enumerate(results):
            # Typesense may wrap the actual document in a 'document' field
            doc = item.get("document", item) if isinstance(item, dict) else item

            # Log first item structure for debugging
            if idx == 0:
                logger.debug(f"🔍 First result keys: {list(doc.keys()) if isinstance(doc, dict) else 'Not a dict'}")

            # Extract fields with defensive fallbacks
            series_list.append({
                "series_id": doc.get("id"),
                "series_name": doc.get("name", ""),
                "author_name": doc.get("author_name", ""),
                "book_count": doc.get("primary_books_count", doc.get("books_count", doc.get("book_count", 0))),
                "readers_count": doc.get("readers_count", 0)
            })

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
        List all books in a series.

        Args:
            series_id: Hardcover series ID

        Returns:
            Dictionary with keys:
            - series_id, series_name: Series metadata
            - books: List of book dictionaries with title, position, authors, etc.
        """
        if not self.is_configured:
            return None

        # Generate cache key
        cache_key = self._get_cache_key("series", str(series_id))

        # Check cache
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        # Build GraphQL query
        query = """
        query GetSeriesBooks($seriesId: Int!) {
          series_by_pk(id: $seriesId) {
            id
            name
            author_name
            books(order_by: {position: asc}) {
              id
              title
              subtitle
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
        """

        variables = {"seriesId": series_id}

        logger.info(f"📚 Fetching books for series ID {series_id}")

        # Execute query
        data = await self._execute_graphql(query, variables)

        if not data or "series_by_pk" not in data or not data["series_by_pk"]:
            logger.warning(f"⚠️  Series {series_id} not found")
            return None

        series_data = data["series_by_pk"]

        # Transform books
        books = []
        for book in series_data.get("books", []):
            authors = [a["name"] for a in book.get("authors", [])]

            books.append({
                "book_id": book["id"],
                "title": book["title"],
                "subtitle": book.get("subtitle", ""),
                "position": book.get("position"),
                "published_year": book.get("published_year"),
                "cover_url": book.get("image", ""),
                "authors": authors
            })

        result = {
            "series_id": series_data["id"],
            "series_name": series_data["name"],
            "author_name": series_data.get("author_name", ""),
            "books": books
        }

        logger.info(f"✅ Found {len(books)} books in series '{series_data['name']}'")

        # Cache results
        await self._set_cache(
            cache_key,
            "books",
            result,
            {
                "series_id": series_id,
                "series_name": series_data["name"],
                "series_author": series_data.get("author_name", "")
            }
        )

        return result


# Global instance
hardcover_client = HardcoverClient()
