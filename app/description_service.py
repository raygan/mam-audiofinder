"""
Unified Description Service for MAM Audiobook Finder.
Coordinates description fetching from multiple sources with fallback logic.
"""
import logging
import time
import json
from typing import Optional, Dict, Any
from datetime import datetime

from config import DESCRIPTION_FALLBACK_ENABLED, DESCRIPTION_CACHE_TTL

logger = logging.getLogger("mam-audiofinder")


class DescriptionService:
    """
    Unified service for fetching book descriptions from multiple sources.

    Implements cascading fallback: ABS → Hardcover → None
    Provides unified caching and source tracking.
    """

    def __init__(self):
        """Initialize description service."""
        # In-memory cache: {cache_key: (result, timestamp)}
        self._cache: Dict[str, tuple] = {}
        self.fallback_enabled = DESCRIPTION_FALLBACK_ENABLED
        self.cache_ttl = DESCRIPTION_CACHE_TTL

    def _get_cache_key(
        self,
        title: str,
        author: str = "",
        asin: str = "",
        isbn: str = "",
        abs_item_id: str = None
    ) -> str:
        """Generate cache key for a book description request."""
        # Use abs_item_id if available for most specific key
        if abs_item_id:
            return f"desc:abs:{abs_item_id}"

        # Use ASIN/ISBN if available
        if asin:
            return f"desc:asin:{asin.lower()}"
        if isbn:
            return f"desc:isbn:{isbn.lower()}"

        # Fallback to title+author
        key_parts = [title.lower().strip()]
        if author:
            key_parts.append(author.lower().strip())
        return f"desc:title:{'|'.join(key_parts)}"

    async def get_description(
        self,
        title: str,
        author: str = "",
        asin: str = "",
        isbn: str = "",
        abs_item_id: str = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get book description from available sources with fallback.

        Tries sources in order:
        1. In-memory cache (if not force_refresh)
        2. Audiobookshelf (if configured)
        3. Hardcover API (if configured and fallback enabled)

        Args:
            title: Book title (required)
            author: Author name (optional, improves matching)
            asin: Amazon ASIN (optional, best for ABS matching)
            isbn: ISBN (optional, good for ABS matching)
            abs_item_id: Direct ABS item ID (optional, most specific)
            force_refresh: Skip cache and force fresh fetch

        Returns:
            Dictionary with:
            - description: Text description (empty string if none found)
            - source: "abs" | "hardcover" | "none"
            - metadata: Full metadata from source (if available)
            - cached: True if from cache, False if fresh fetch
            - fetched_at: ISO timestamp of fetch
        """
        if not title:
            logger.warning("⚠️  No title provided for description fetch")
            return {
                "description": "",
                "source": "none",
                "metadata": {},
                "cached": False,
                "fetched_at": datetime.utcnow().isoformat() + "Z"
            }

        # Generate cache key
        cache_key = self._get_cache_key(title, author, asin, isbn, abs_item_id)

        # Check in-memory cache
        if not force_refresh and cache_key in self._cache:
            cached_result, cached_time = self._cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.info(f"✅ Description cache HIT for '{title}' (source: {cached_result.get('source')})")
                cached_result["cached"] = True
                return cached_result

        logger.info(f"🔍 Fetching description for: '{title}' by '{author}'")

        # Try ABS first (if configured)
        abs_result = await self._try_abs(title, author, asin, isbn, abs_item_id)
        if abs_result and abs_result.get("description"):
            result = {
                "description": abs_result["description"],
                "source": "abs",
                "metadata": abs_result.get("metadata", {}),
                "cached": False,
                "fetched_at": datetime.utcnow().isoformat() + "Z"
            }
            # Cache the result
            self._cache[cache_key] = (result, time.time())
            logger.info(f"✅ Got description from ABS for '{title}' ({len(result['description'])} chars)")
            return result

        # Try Hardcover fallback (if enabled and configured)
        if self.fallback_enabled:
            hardcover_result = await self._try_hardcover(title, author)
            if hardcover_result and hardcover_result.get("description"):
                result = {
                    "description": hardcover_result["description"],
                    "source": "hardcover",
                    "metadata": {
                        "book_id": hardcover_result.get("book_id"),
                        "title": hardcover_result.get("title"),
                        "authors": hardcover_result.get("authors", []),
                        "series_names": hardcover_result.get("series_names", []),
                        "published_year": hardcover_result.get("published_year")
                    },
                    "cached": False,
                    "fetched_at": datetime.utcnow().isoformat() + "Z"
                }
                # Cache the result
                self._cache[cache_key] = (result, time.time())
                logger.info(f"✅ Got description from Hardcover for '{title}' ({len(result['description'])} chars)")
                return result

        # No description found from any source
        logger.info(f"ℹ️  No description found for '{title}' from any source")
        result = {
            "description": "",
            "source": "none",
            "metadata": {},
            "cached": False,
            "fetched_at": datetime.utcnow().isoformat() + "Z"
        }
        return result

    async def _try_abs(
        self,
        title: str,
        author: str,
        asin: str,
        isbn: str,
        abs_item_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Try to fetch description from Audiobookshelf.

        Returns dict with description and metadata, or None if ABS not configured/failed.
        """
        try:
            # Import here to avoid circular dependency
            from abs_client import abs_client

            if not abs_client.is_configured:
                logger.debug("⏭️  ABS not configured, skipping")
                return None

            # If we have abs_item_id, fetch directly
            if abs_item_id:
                logger.info(f"🔍 Fetching from ABS by item_id: {abs_item_id}")
                item_details = await abs_client.fetch_item_details(abs_item_id)
                if item_details:
                    return item_details

            # Otherwise, search for the book in library
            logger.info(f"🔍 Searching ABS library for: '{title}' by '{author}'")

            # Fetch library items
            library_items = await abs_client._get_cached_library_items()

            if not library_items:
                logger.debug("⚠️  No library items found in ABS")
                return None

            # Search for matching item using similar logic to verify_import
            title_lower = title.lower().strip()
            author_lower = author.lower().strip() if author else ""

            best_match = None
            best_score = 0

            for item in library_items:
                item_metadata = item.get("media", {}).get("metadata", {})
                item_title = (item_metadata.get("title") or "").lower().strip()
                item_author = (item_metadata.get("authorName") or "").lower().strip()
                item_asin = (item_metadata.get("asin") or "").lower().strip()
                item_isbn = (item_metadata.get("isbn") or "").lower().strip()
                item_id = item.get("id")

                score = 0
                title_match = False

                # ASIN/ISBN matching (highest priority)
                if asin and item_asin and asin.lower() == item_asin:
                    score += 200
                    title_match = True
                    logger.debug(f"🎯 ASIN match found: {asin}")
                elif isbn and item_isbn and isbn.lower() == item_isbn:
                    score += 200
                    title_match = True
                    logger.debug(f"🎯 ISBN match found: {isbn}")
                else:
                    # Title matching
                    if item_title == title_lower:
                        score += 100
                        title_match = True
                    elif title_lower in item_title or item_title in title_lower:
                        score += 50
                        title_match = True

                    # Author matching
                    if author_lower:
                        if item_author == author_lower:
                            score += 50
                        elif author_lower in item_author or item_author in author_lower:
                            score += 25

                # Update best match
                if score > best_score and title_match:
                    best_score = score
                    best_match = {
                        "item_id": item_id,
                        "title": item_metadata.get("title"),
                        "author": item_metadata.get("authorName"),
                        "score": score
                    }

            # If we found a good match (score >= 50), fetch full details
            if best_match and best_score >= 50:
                logger.info(f"✅ Found ABS match: '{best_match['title']}' (score: {best_score})")
                item_details = await abs_client.fetch_item_details(best_match["item_id"])
                return item_details

            logger.debug(f"⚠️  No good ABS match found (best score: {best_score})")
            return None

        except Exception as e:
            logger.error(f"❌ ABS description fetch failed: {type(e).__name__}: {e}")
            return None

    async def _try_hardcover(
        self,
        title: str,
        author: str
    ) -> Optional[Dict[str, Any]]:
        """
        Try to fetch description from Hardcover API.

        Returns dict with description and metadata, or None if Hardcover not configured/failed.
        """
        try:
            # Import here to avoid circular dependency
            from hardcover_client import hardcover_client

            if not hardcover_client.is_configured:
                logger.debug("⏭️  Hardcover not configured, skipping")
                return None

            logger.info(f"🔍 Searching Hardcover for: '{title}' by '{author}'")

            # Search for book
            book_result = await hardcover_client.search_book_by_title(title, author)

            if book_result:
                logger.info(f"✅ Found Hardcover book: '{book_result.get('title')}'")
                return book_result

            logger.debug(f"⚠️  No Hardcover match found for '{title}'")
            return None

        except Exception as e:
            logger.error(f"❌ Hardcover description fetch failed: {type(e).__name__}: {e}")
            return None

    def clear_cache(self):
        """Clear in-memory description cache."""
        self._cache.clear()
        logger.info("🗑️  Cleared description service cache")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = time.time()
        valid_entries = sum(
            1 for _, (_, cached_time) in self._cache.items()
            if current_time - cached_time < self.cache_ttl
        )

        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "cache_ttl": self.cache_ttl,
            "fallback_enabled": self.fallback_enabled
        }


# Global instance
description_service = DescriptionService()
