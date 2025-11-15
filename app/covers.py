"""
Cover management service for MAM Audiobook Finder.
Handles cover caching, downloading, and serving.
"""
import logging
import httpx
from pathlib import Path
from datetime import datetime
from sqlalchemy import text

from config import COVERS_DIR, MAX_COVERS_SIZE_MB, ABS_BASE_URL, ABS_API_KEY
from db import covers_engine, engine

logger = logging.getLogger("mam-audiofinder")


class CoverService:
    """Service for managing cover images with caching."""

    def __init__(self):
        """Initialize cover service and ensure directories exist."""
        COVERS_DIR.mkdir(parents=True, exist_ok=True)

    def get_covers_dir_size(self) -> int:
        """Get total size of covers directory in bytes."""
        total_size = 0
        try:
            for file in COVERS_DIR.iterdir():
                if file.is_file():
                    total_size += file.stat().st_size
        except Exception as e:
            logger.warning(f"⚠️  Error calculating covers directory size: {e}")
        return total_size

    def cleanup_old_covers(self):
        """Remove oldest covers if directory exceeds MAX_COVERS_SIZE_MB."""
        if MAX_COVERS_SIZE_MB == 0:
            # No caching - should never get here, but just in case
            return

        max_bytes = MAX_COVERS_SIZE_MB * 1024 * 1024
        current_size = self.get_covers_dir_size()

        if current_size <= max_bytes:
            return

        logger.info(f"📦 Covers cache ({current_size / 1024 / 1024:.1f}MB) exceeds limit ({MAX_COVERS_SIZE_MB}MB), cleaning up...")

        # Get all cover files with their access times
        files_with_times = []
        try:
            for file in COVERS_DIR.iterdir():
                if file.is_file():
                    files_with_times.append((file, file.stat().st_atime, file.stat().st_size))
        except Exception as e:
            logger.error(f"❌ Error listing covers for cleanup: {e}")
            return

        # Sort by access time (oldest first)
        files_with_times.sort(key=lambda x: x[1])

        # Remove oldest files until we're under the limit
        removed_count = 0
        removed_size = 0
        for file, _, size in files_with_times:
            if current_size - removed_size <= max_bytes:
                break
            try:
                file.unlink()
                removed_count += 1
                removed_size += size
                logger.info(f"🗑️  Removed old cover: {file.name} ({size / 1024:.1f}KB)")
            except Exception as e:
                logger.warning(f"⚠️  Failed to remove {file.name}: {e}")

        if removed_count > 0:
            logger.info(f"✅ Cleaned up {removed_count} covers, freed {removed_size / 1024 / 1024:.1f}MB")

    async def download_cover(self, url: str, mam_id: str) -> tuple[str | None, int]:
        """
        Download cover image and save to local storage.
        Returns tuple of (local_file_path, file_size) or (None, 0) on failure.
        """
        if MAX_COVERS_SIZE_MB == 0:
            # Direct fetch mode - don't cache
            logger.info(f"ℹ️  MAX_COVERS_SIZE_MB=0, skipping download for direct fetch mode")
            return None, 0

        try:
            logger.info(f"⬇️  Downloading cover from: {url}")

            async with httpx.AsyncClient(timeout=30) as client:
                # Add auth header if it's an ABS URL
                headers = {}
                if ABS_BASE_URL and url.startswith(ABS_BASE_URL):
                    headers["Authorization"] = f"Bearer {ABS_API_KEY}"

                r = await client.get(url, headers=headers, follow_redirects=True)

                if r.status_code != 200:
                    logger.warning(f"⚠️  Failed to download cover: HTTP {r.status_code}")
                    return None, 0

                # Determine file extension from Content-Type or URL
                content_type = r.headers.get("Content-Type", "")
                ext = ".jpg"  # default
                if "png" in content_type:
                    ext = ".png"
                elif "webp" in content_type:
                    ext = ".webp"
                elif "gif" in content_type:
                    ext = ".gif"
                elif url.endswith(".png"):
                    ext = ".png"
                elif url.endswith(".webp"):
                    ext = ".webp"

                # Save to file
                filename = f"{mam_id}{ext}"
                filepath = COVERS_DIR / filename
                file_size = len(r.content)

                filepath.write_bytes(r.content)
                logger.info(f"✅ Saved cover: {filename} ({file_size / 1024:.1f}KB)")

                # Check if we need to cleanup old covers
                self.cleanup_old_covers()

                return str(filepath), file_size

        except Exception as e:
            logger.error(f"❌ Failed to download cover from {url}: {type(e).__name__}: {e}")
            logger.exception("Cover download traceback:")
            return None, 0

    def get_cached_cover(self, mam_id: str) -> dict:
        """
        Get cached cover from covers database by MAM ID.
        Returns dict with 'cover_url' (local or remote), 'item_id', 'is_local' if found, else empty dict.
        """
        if not mam_id:
            logger.warning(f"⚠️  get_cached_cover called with empty mam_id")
            return {}

        try:
            with covers_engine.begin() as cx:
                row = cx.execute(text("""
                    SELECT cover_url, abs_item_id, fetched_at, title, author, local_file
                    FROM covers
                    WHERE mam_id = :mam_id
                    LIMIT 1
                """), {"mam_id": mam_id}).fetchone()

                if row and row[0]:
                    local_file = row[5]
                    # Check if local file exists
                    if local_file and Path(local_file).exists():
                        # Return local cover path
                        filename = Path(local_file).name
                        local_url = f"/covers/{filename}"
                        logger.info(f"📦 Cache HIT (local) for MAM ID {mam_id}: {local_url} (title: '{row[3]}', fetched: {row[2]})")
                        return {"cover_url": local_url, "item_id": row[1], "is_local": True}
                    elif MAX_COVERS_SIZE_MB == 0:
                        # Direct fetch mode - return remote URL
                        logger.info(f"📦 Cache HIT (direct) for MAM ID {mam_id}: {row[0]} (title: '{row[3]}', fetched: {row[2]})")
                        return {"cover_url": row[0], "item_id": row[1], "is_local": False}
                    else:
                        # Local file missing but should exist - return remote URL as fallback
                        logger.warning(f"⚠️  Cache HIT but local file missing for MAM ID {mam_id}, using remote URL")
                        return {"cover_url": row[0], "item_id": row[1], "is_local": False}

            logger.info(f"📦 Cache MISS for MAM ID {mam_id}")
            return {}
        except Exception as e:
            logger.error(f"❌ CRITICAL: Failed to get cached cover for MAM ID {mam_id}: {type(e).__name__}: {e}")
            logger.exception("Get cached cover traceback:")
            return {}

    async def save_cover_to_cache(self, mam_id: str, cover_url: str, title: str = "", author: str = "", item_id: str = None):
        """
        Save cover URL to covers database and download the image to local storage.
        Uses INSERT OR REPLACE to handle duplicates.
        Also checks if the cover_url is already used by another MAM ID to avoid duplicate downloads.
        """
        if not mam_id:
            logger.warning(f"⚠️  save_cover_to_cache called with empty mam_id")
            return

        if not cover_url:
            logger.warning(f"⚠️  save_cover_to_cache called with empty cover_url for MAM ID {mam_id}")
            return

        try:
            logger.info(f"💾 Attempting to cache cover for MAM ID {mam_id}: {cover_url}")

            local_file = None
            file_size = 0

            # Check if we should download the cover (do this in a separate connection block)
            existing = None
            with covers_engine.begin() as cx:
                # Check if this cover URL is already cached for a different MAM ID
                existing = cx.execute(text("""
                    SELECT mam_id, title, local_file, file_size FROM covers
                    WHERE cover_url = :cover_url AND mam_id != :mam_id LIMIT 1
                """), {"cover_url": cover_url, "mam_id": mam_id}).fetchone()
            # Connection is now closed before we do any async operations

            # Process the result AFTER closing the connection
            if existing and existing[2]:
                # Reuse existing downloaded cover
                local_file = existing[2]
                file_size = existing[3] or 0
                logger.info(f"ℹ️  Cover URL already cached for MAM ID {existing[0]} ('{existing[1]}'). Reusing local file: {Path(local_file).name}")
            elif MAX_COVERS_SIZE_MB > 0:
                # Download the cover (no DB connection held during this async operation)
                local_file, file_size = await self.download_cover(cover_url, mam_id)

            # Get the final cover URL (local or remote)
            final_cover_url = cover_url
            if local_file and Path(local_file).exists():
                filename = Path(local_file).name
                final_cover_url = f"/covers/{filename}"

            # Insert or replace the cover entry (separate connection block)
            with covers_engine.begin() as cx:
                cx.execute(text("""
                    INSERT INTO covers (mam_id, title, author, cover_url, abs_item_id, local_file, file_size, fetched_at)
                    VALUES (:mam_id, :title, :author, :cover_url, :item_id, :local_file, :file_size, :fetched_at)
                    ON CONFLICT(mam_id) DO UPDATE SET
                        cover_url = :cover_url,
                        abs_item_id = :item_id,
                        title = :title,
                        author = :author,
                        local_file = :local_file,
                        file_size = :file_size,
                        fetched_at = :fetched_at
                """), {
                    "mam_id": mam_id,
                    "title": title,
                    "author": author,
                    "cover_url": cover_url,  # Keep original remote URL
                    "item_id": item_id,
                    "local_file": local_file,
                    "file_size": file_size,
                    "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                })

                logger.info(f"✅ Cached cover for MAM ID {mam_id}: {final_cover_url}")

            # Also update history table if there's an entry (separate connection block)
            try:
                with engine.begin() as cx:
                    result = cx.execute(text("""
                        UPDATE history
                        SET abs_cover_url = :cover_url,
                            abs_item_id = :item_id,
                            abs_cover_cached_at = :cached_at
                        WHERE mam_id = :mam_id
                    """), {
                        "mam_id": mam_id,
                        "cover_url": final_cover_url,  # Use local URL if available
                        "item_id": item_id,
                        "cached_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    if result.rowcount > 0:
                        logger.info(f"✅ Updated {result.rowcount} history row(s) with cover for MAM ID {mam_id}")
            except Exception as he:
                logger.warning(f"⚠️  Failed to update history table (non-critical): {he}")

        except Exception as e:
            logger.error(f"❌ CRITICAL: Failed to cache cover for MAM ID {mam_id}: {type(e).__name__}: {e}")
            logger.exception("Save cover to cache traceback:")


# Global instance
cover_service = CoverService()
