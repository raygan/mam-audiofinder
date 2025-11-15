"""
Audiobookshelf API client for MAM Audiobook Finder.
Handles API communication with Audiobookshelf server.
"""
import logging
import httpx
from typing import Optional

from config import ABS_BASE_URL, ABS_API_KEY, ABS_LIBRARY_ID
from covers import cover_service

logger = logging.getLogger("mam-audiofinder")


class AudiobookshelfClient:
    """Client for interacting with Audiobookshelf API."""

    def __init__(self):
        """Initialize Audiobookshelf client."""
        self.base_url = ABS_BASE_URL
        self.api_key = ABS_API_KEY
        self.library_id = ABS_LIBRARY_ID

    @property
    def is_configured(self) -> bool:
        """Check if Audiobookshelf is configured."""
        return bool(self.base_url and self.api_key)

    async def test_connection(self) -> bool:
        """Test Audiobookshelf API connectivity."""
        if not self.is_configured:
            logger.info("ℹ️  Audiobookshelf integration not configured (skipping connectivity test)")
            return False

        try:
            logger.info(f"🔍 Testing Audiobookshelf API connection to {self.base_url}...")
            headers = {"Authorization": f"Bearer {self.api_key}"}

            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self.base_url}/api/me", headers=headers)

                if r.status_code == 200:
                    data = r.json()
                    username = data.get("username", "unknown")
                    logger.info(f"✅ Audiobookshelf API connected successfully (user: {username})")
                    return True
                else:
                    logger.error(f"❌ Audiobookshelf API test failed: HTTP {r.status_code}")
                    logger.error(f"   Response: {r.text[:200]}")
                    return False

        except Exception as e:
            logger.error(f"❌ Audiobookshelf API test failed with exception: {e}")
            return False

    async def fetch_cover(self, title: str, author: str = "", mam_id: str = "") -> dict:
        """
        Fetch cover image URL from Audiobookshelf.
        Returns dict with 'cover_url' and 'item_id' if found, else empty dict.
        Checks cache first if mam_id is provided.
        """
        logger.info(f"🔍 Fetching cover for: '{title}' by '{author}' (MAM ID: {mam_id or 'N/A'})")

        # Check cache first
        if mam_id:
            cached = cover_service.get_cached_cover(mam_id)
            if cached:
                return cached

        if not self.is_configured:
            logger.warning(f"⚠️  ABS not configured, skipping cover fetch for '{title}'")
            return {}

        if not title:
            logger.warning(f"⚠️  No title provided, skipping cover fetch")
            return {}

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            params = {"title": title}
            if author:
                params["author"] = author

            logger.info(f"🌐 Calling ABS /api/search/covers with params: {params}")

            async with httpx.AsyncClient(timeout=10) as client:
                # Try the search/covers endpoint first
                r = await client.get(
                    f"{self.base_url}/api/search/covers",
                    headers=headers,
                    params=params
                )

                logger.info(f"📡 ABS /api/search/covers response: HTTP {r.status_code}")

                if r.status_code == 200:
                    data = r.json()
                    results = data.get("results", [])
                    logger.info(f"📊 Got {len(results)} results from /api/search/covers")

                    if results and len(results) > 0:
                        # Take the first result
                        first_result = results[0]
                        cover_url = None
                        if isinstance(first_result, str):
                            # It's just a URL
                            cover_url = first_result
                            logger.info(f"✅ Found cover URL (string): {cover_url}")
                        elif isinstance(first_result, dict):
                            # It might have more structure
                            cover_url = first_result.get("cover") or first_result.get("url") or str(first_result)
                            logger.info(f"✅ Found cover URL (dict): {cover_url}")

                        if cover_url:
                            # Cache the result if we have a MAM ID
                            if mam_id:
                                await cover_service.save_cover_to_cache(mam_id, cover_url, title, author, None)
                                # Get the potentially updated cover URL (local path)
                                cached = cover_service.get_cached_cover(mam_id)
                                if cached:
                                    return cached
                            return {"cover_url": cover_url, "item_id": None}
                    else:
                        logger.warning(f"⚠️  No results from /api/search/covers")
                else:
                    logger.warning(f"⚠️  /api/search/covers failed: {r.text[:200]}")

            # If no results from search/covers, try searching library items
            if self.library_id:
                logger.info(f"🔍 Trying library search with ID: {self.library_id}")
                async with httpx.AsyncClient(timeout=10) as client:
                    # Search within library using filter
                    r = await client.get(
                        f"{self.base_url}/api/libraries/{self.library_id}/items",
                        headers=headers,
                        params={"limit": 5, "minified": "1"}
                    )

                    logger.info(f"📡 ABS library items response: HTTP {r.status_code}")

                    if r.status_code == 200:
                        data = r.json()
                        results = data.get("results", [])
                        logger.info(f"📊 Got {len(results)} items from library")

                        # Simple title matching (case-insensitive)
                        title_lower = title.lower()
                        for item in results:
                            item_title = (item.get("media", {}).get("metadata", {}).get("title") or "").lower()
                            if title_lower in item_title or item_title in title_lower:
                                item_id = item.get("id")
                                if item_id:
                                    # Build cover URL
                                    cover_url = f"{self.base_url}/api/items/{item_id}/cover"
                                    logger.info(f"✅ Found cover in library: {cover_url}")
                                    # Cache the result if we have a MAM ID
                                    if mam_id:
                                        await cover_service.save_cover_to_cache(mam_id, cover_url, title, author, item_id)
                                        # Get the potentially updated cover URL (local path)
                                        cached = cover_service.get_cached_cover(mam_id)
                                        if cached:
                                            return cached
                                    return {"cover_url": cover_url, "item_id": item_id}
                        logger.warning(f"⚠️  No matching items in library for '{title}'")
                    else:
                        logger.warning(f"⚠️  Library search failed: {r.text[:200]}")
            else:
                logger.info(f"ℹ️  No ABS_LIBRARY_ID configured, skipping library search")

            logger.warning(f"❌ No cover found for '{title}'")
            return {}

        except Exception as e:
            # Don't fail the whole request if ABS is down
            logger.error(f"❌ Audiobookshelf cover fetch failed for '{title}': {type(e).__name__}: {e}")
            return {}


# Global instance
abs_client = AudiobookshelfClient()
