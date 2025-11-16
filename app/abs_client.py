"""
Audiobookshelf API client for MAM Audiobook Finder.
Handles API communication with Audiobookshelf server.
"""
import logging
import httpx
from typing import Optional

from config import ABS_BASE_URL, ABS_API_KEY, ABS_LIBRARY_ID, ABS_VERIFY_TIMEOUT
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

    async def fetch_cover(self, title: str, author: str = "", mam_id: str = "", force_refresh: bool = False) -> dict:
        """
        Fetch cover image URL from Audiobookshelf.
        Returns dict with 'cover_url' and 'item_id' if found, else empty dict.
        Checks cache first if mam_id is provided.
        """
        logger.info(f"🔍 Fetching cover for: '{title}' by '{author}' (MAM ID: {mam_id or 'N/A'})")

        # Check cache first
        if mam_id and not force_refresh:
            cached = cover_service.get_cached_cover(mam_id)
            if cached:
                if cached.get("needs_heal") and cached.get("source_cover_url"):
                    logger.info(f"🩹 Healing missing cover file for MAM ID {mam_id}")
                    await cover_service.save_cover_to_cache(
                        mam_id,
                        cached.get("source_cover_url"),
                        cached.get("title") or title,
                        cached.get("author") or author,
                        cached.get("item_id")
                    )
                    healed = cover_service.get_cached_cover(mam_id)
                    if healed:
                        cached = healed
                if cached.get("cover_url"):
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

    async def verify_import(self, title: str, author: str = "", library_path: str = "", metadata: dict = None) -> dict:
        """
        Verify that an imported item exists in Audiobookshelf library.

        Args:
            title: Book title (from torrent or metadata.json)
            author: Author name (from torrent or metadata.json)
            library_path: Path where book was imported
            metadata: Optional dict from metadata.json with enhanced matching data

        Returns dict with:
            - status: 'verified', 'mismatch', 'not_found', 'unreachable', or 'not_configured'
            - note: Diagnostic message explaining the status
            - abs_item_id: ABS item ID if found, else None

        Implements retry logic with exponential backoff (max 3 attempts).
        """
        logger.info(f"🔍 Verifying import in ABS: '{title}' by '{author}' at '{library_path}'")

        # Check if ABS is configured
        if not self.is_configured:
            logger.info("ℹ️  Audiobookshelf not configured, skipping verification")
            return {
                "status": "not_configured",
                "note": "ABS integration not configured",
                "abs_item_id": None
            }

        if not self.library_id:
            logger.warning("⚠️  ABS_LIBRARY_ID not configured, cannot verify import")
            return {
                "status": "not_configured",
                "note": "ABS_LIBRARY_ID not configured",
                "abs_item_id": None
            }

        if not title:
            logger.warning("⚠️  No title provided for verification")
            return {
                "status": "not_found",
                "note": "No title provided",
                "abs_item_id": None
            }

        # Retry logic with exponential backoff (max 3 attempts)
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                headers = {"Authorization": f"Bearer {self.api_key}"}

                logger.info(f"🌐 Calling ABS /api/libraries/{self.library_id}/items (attempt {attempt}/{max_attempts})")

                async with httpx.AsyncClient(timeout=ABS_VERIFY_TIMEOUT) as client:
                    # Search library items
                    r = await client.get(
                        f"{self.base_url}/api/libraries/{self.library_id}/items",
                        headers=headers,
                        params={"limit": 20, "minified": "0"}  # Get full metadata for comparison
                    )

                    logger.info(f"📡 ABS library items response: HTTP {r.status_code}")

                    if r.status_code != 200:
                        logger.warning(f"⚠️  Library search failed: {r.text[:200]}")
                        # If this is the last attempt, return unreachable
                        if attempt == max_attempts:
                            return {
                                "status": "unreachable",
                                "note": f"ABS API returned HTTP {r.status_code}",
                                "abs_item_id": None
                            }
                        # Otherwise, retry with exponential backoff
                        import asyncio
                        wait_time = 2 ** (attempt - 1)  # 1s, 2s, 4s
                        logger.info(f"⏳ Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue

                    data = r.json()
                    results = data.get("results", [])
                    logger.info(f"📊 Got {len(results)} items from library")

                    # Search for matching items
                    title_lower = title.lower().strip()
                    author_lower = author.lower().strip() if author else ""

                    # Enhanced matching with metadata.json
                    metadata_authors = []
                    metadata_asin = None
                    metadata_isbn = None
                    if metadata:
                        metadata_authors = [a.lower().strip() for a in metadata.get("authors", []) if a]
                        metadata_asin = metadata.get("asin", "")
                        metadata_isbn = metadata.get("isbn", "")

                    best_match = None
                    best_match_score = 0

                    for item in results:
                        item_metadata = item.get("media", {}).get("metadata", {})
                        item_title = (item_metadata.get("title") or "").lower().strip()
                        item_author = (item_metadata.get("authorName") or "").lower().strip()
                        item_asin = (item_metadata.get("asin") or "").lower().strip()
                        item_isbn = (item_metadata.get("isbn") or "").lower().strip()
                        item_id = item.get("id")
                        item_path = item.get("path", "")

                        # Calculate match score
                        score = 0
                        title_match = False
                        author_match = False

                        # ASIN/ISBN matching (highest priority - exact identifier match)
                        if metadata_asin and item_asin and metadata_asin.lower() == item_asin:
                            score += 200  # Very high score for ASIN match
                            title_match = True
                            author_match = True
                            logger.info(f"🎯 ASIN match found: {metadata_asin}")
                        elif metadata_isbn and item_isbn and metadata_isbn.lower() == item_isbn:
                            score += 200  # Very high score for ISBN match
                            title_match = True
                            author_match = True
                            logger.info(f"🎯 ISBN match found: {metadata_isbn}")
                        else:
                            # Exact title match
                            if item_title == title_lower:
                                score += 100
                                title_match = True
                            # Title contains or is contained
                            elif title_lower in item_title or item_title in title_lower:
                                score += 50
                                title_match = True

                            # Author matching with metadata.json support
                            if metadata_authors:
                                # Check if any metadata author matches item author
                                for meta_author in metadata_authors:
                                    if meta_author == item_author:
                                        score += 50
                                        author_match = True
                                        break
                                    elif meta_author in item_author or item_author in meta_author:
                                        score += 25
                                        author_match = True
                                        break
                            elif author_lower:
                                # Fallback to simple author matching
                                if item_author == author_lower:
                                    score += 50
                                    author_match = True
                                elif author_lower in item_author or item_author in author_lower:
                                    score += 25
                                    author_match = True
                            else:
                                # No author to verify, count as match
                                author_match = True
                                score += 10

                            # Path matching (if provided)
                            if library_path and item_path:
                                # Normalize paths for comparison
                                lib_path_norm = library_path.lower().replace("\\", "/").strip("/")
                                item_path_norm = item_path.lower().replace("\\", "/").strip("/")
                                if lib_path_norm in item_path_norm or item_path_norm in lib_path_norm:
                                    score += 25

                        # Update best match if this is better
                        if score > best_match_score and title_match:
                            best_match_score = score
                            best_match = {
                                "item_id": item_id,
                                "title": item_metadata.get("title"),
                                "author": item_metadata.get("authorName"),
                                "path": item_path,
                                "title_match": title_match,
                                "author_match": author_match,
                                "score": score
                            }

                    # Evaluate best match
                    if not best_match:
                        logger.warning(f"❌ No matching item found in ABS for '{title}'")
                        return {
                            "status": "not_found",
                            "note": f"Not found in library",
                            "abs_item_id": None
                        }

                    # Check for mismatches - adjusted thresholds for ASIN/ISBN matches
                    if best_match_score >= 200:
                        # ASIN/ISBN match - highest confidence
                        logger.info(f"✅ Import verified in ABS via ASIN/ISBN: '{best_match['title']}' by '{best_match['author']}' (ID: {best_match['item_id']})")
                        return {
                            "status": "verified",
                            "note": f"ASIN/ISBN match: '{best_match['title']}' by '{best_match['author']}'",
                            "abs_item_id": best_match["item_id"]
                        }
                    elif best_match_score >= 100:
                        # Perfect title + author match
                        logger.info(f"✅ Import verified in ABS: '{best_match['title']}' by '{best_match['author']}' (ID: {best_match['item_id']})")
                        return {
                            "status": "verified",
                            "note": f"Found in library: '{best_match['title']}' by '{best_match['author']}'",
                            "abs_item_id": best_match["item_id"]
                        }
                    else:
                        # Partial match - report as mismatch with details
                        if not best_match["author_match"] and author:
                            note = f"Author mismatch: expected '{author}' found '{best_match['author']}'"
                        elif best_match_score < 50:
                            note = f"Weak match: '{best_match['title']}' (score: {best_match_score})"
                        else:
                            note = f"Partial match: '{best_match['title']}' by '{best_match['author']}' (score: {best_match_score})"

                        logger.warning(f"⚠️  {note}")
                        return {
                            "status": "mismatch",
                            "note": note,
                            "abs_item_id": best_match["item_id"]
                        }

            except httpx.TimeoutException as e:
                logger.error(f"⏱️  ABS verification timeout (attempt {attempt}/{max_attempts}): {e}")
                if attempt == max_attempts:
                    return {
                        "status": "unreachable",
                        "note": f"Timeout after {max_attempts} attempts",
                        "abs_item_id": None
                    }
                # Retry with exponential backoff
                import asyncio
                wait_time = 2 ** (attempt - 1)
                logger.info(f"⏳ Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue

            except Exception as e:
                # Don't fail the import if verification errors
                logger.error(f"❌ ABS verification failed (attempt {attempt}/{max_attempts}): {type(e).__name__}: {e}")
                if attempt == max_attempts:
                    return {
                        "status": "unreachable",
                        "note": f"Error: {type(e).__name__}: {str(e)[:100]}",
                        "abs_item_id": None
                    }
                # Retry with exponential backoff
                import asyncio
                wait_time = 2 ** (attempt - 1)
                logger.info(f"⏳ Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue

        # Should never reach here, but just in case
        return {
            "status": "unreachable",
            "note": "Unknown error during verification",
            "abs_item_id": None
        }


# Global instance
abs_client = AudiobookshelfClient()
