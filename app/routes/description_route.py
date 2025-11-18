"""
Description routes for unified description fetching.
Handles description retrieval from multiple sources (ABS, Hardcover).
"""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from description_service import description_service

router = APIRouter()
logger = logging.getLogger("mam-audiofinder")


class DescriptionFetchRequest(BaseModel):
    """Request model for description fetch."""
    title: str
    author: str = ""
    asin: str = ""
    isbn: str = ""
    abs_item_id: Optional[str] = None
    force_refresh: bool = False


@router.post("/api/description/fetch")
async def fetch_description(request: DescriptionFetchRequest):
    """
    Fetch book description from available sources with fallback.

    Tries sources in order:
    1. In-memory cache (unless force_refresh=true)
    2. Audiobookshelf (if configured)
    3. Hardcover API (if configured and fallback enabled)

    Request:
        {
            "title": "The Way of Kings",           // required
            "author": "Brandon Sanderson",         // optional
            "asin": "B003P2WO5E",                  // optional
            "isbn": "9780765365279",               // optional
            "abs_item_id": "li_abc123",            // optional (ABS item ID)
            "force_refresh": false                 // optional (skip cache)
        }

    Response:
        {
            "description": "...",
            "source": "abs" | "hardcover" | "none",
            "metadata": {...},
            "cached": true/false,
            "fetched_at": "2025-11-18T10:30:00Z"
        }
    """
    if not request.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")

    logger.info(f"📖 Description fetch request: title='{request.title}', author='{request.author}'")

    try:
        result = await description_service.get_description(
            title=request.title,
            author=request.author,
            asin=request.asin,
            isbn=request.isbn,
            abs_item_id=request.abs_item_id,
            force_refresh=request.force_refresh
        )

        logger.info(f"✅ Description fetch returned: source={result['source']}, cached={result['cached']}, "
                   f"length={len(result['description'])} chars")

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"❌ Description fetch failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Description fetch failed: {str(e)}"
        )


@router.get("/api/description/stats")
async def get_description_stats():
    """
    Get description service cache statistics.

    Response:
        {
            "total_entries": 42,
            "valid_entries": 38,
            "cache_ttl": 86400,
            "fallback_enabled": true
        }
    """
    try:
        stats = description_service.get_cache_stats()
        return JSONResponse(stats)

    except Exception as e:
        logger.error(f"❌ Failed to get description stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get stats: {str(e)}"
        )


@router.post("/api/description/cache/clear")
async def clear_description_cache():
    """
    Clear the description service in-memory cache.

    Response:
        {
            "success": true,
            "message": "Description cache cleared"
        }
    """
    try:
        description_service.clear_cache()
        logger.info("✅ Description cache cleared via API")

        return JSONResponse({
            "success": True,
            "message": "Description cache cleared"
        })

    except Exception as e:
        logger.error(f"❌ Failed to clear description cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear cache: {str(e)}"
        )
