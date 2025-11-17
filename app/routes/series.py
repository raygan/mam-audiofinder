"""
Series routes for Hardcover API integration.
Handles series discovery and book listings.
"""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from hardcover_client import hardcover_client
from utils import normalize_title, normalize_author

router = APIRouter()
logger = logging.getLogger("mam-audiofinder")


class SeriesSearchRequest(BaseModel):
    """Request model for series search."""
    title: str
    author: str = ""
    normalized_title: Optional[str] = None
    limit: int = 10


@router.post("/api/series/search")
async def search_series(request: SeriesSearchRequest):
    """
    Search for series on Hardcover by title and/or author.

    Request:
        {
            "title": "The Way of Kings",
            "author": "Brandon Sanderson",  // optional
            "normalized_title": "way of kings",  // optional, will be computed if not provided
            "limit": 10  // optional, default 10
        }

    Response:
        {
            "query": {
                "title": "The Way of Kings",
                "author": "Brandon Sanderson",
                "normalized_title": "way of kings"
            },
            "hardcover_series": [
                {
                    "series_id": 49075,
                    "series_name": "The Stormlight Archive",
                    "author_name": "Brandon Sanderson",
                    "book_count": 5,
                    "readers_count": 125000
                }
            ],
            "cached": false,
            "timestamp": "2025-11-17T10:30:00Z"
        }
    """
    if not hardcover_client.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Hardcover API not configured. Set HARDCOVER_API_TOKEN in environment."
        )

    if not request.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")

    # Compute normalized title if not provided
    normalized_title = request.normalized_title or normalize_title(request.title)

    logger.info(f"📖 Series search request: title='{request.title}', author='{request.author}'")

    try:
        # Search Hardcover for series
        series_results = await hardcover_client.search_series(
            title=request.title,
            author=request.author,
            limit=request.limit
        )

        from datetime import datetime
        response = {
            "query": {
                "title": request.title,
                "author": request.author,
                "normalized_title": normalized_title
            },
            "hardcover_series": series_results,
            "cached": False,  # TODO: Detect cache hit from client
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        logger.info(f"✅ Series search returned {len(series_results)} results")
        return JSONResponse(response)

    except Exception as e:
        logger.error(f"❌ Series search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Series search failed: {str(e)}"
        )


@router.get("/api/series/{series_id}/books")
async def get_series_books(series_id: int):
    """
    Get all books in a series from Hardcover.

    Path parameter:
        series_id: Hardcover series ID

    Response:
        {
            "series_id": 49075,
            "series_name": "The Stormlight Archive",
            "author_name": "Brandon Sanderson",
            "books": [
                {
                    "book_id": 123,
                    "title": "The Way of Kings",
                    "subtitle": "",
                    "position": 1.0,
                    "published_year": 2010,
                    "cover_url": "https://...",
                    "authors": ["Brandon Sanderson"]
                },
                ...
            ],
            "cached": false,
            "timestamp": "2025-11-17T10:30:00Z"
        }
    """
    if not hardcover_client.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Hardcover API not configured. Set HARDCOVER_API_TOKEN in environment."
        )

    logger.info(f"📚 Fetching books for series ID {series_id}")

    try:
        result = await hardcover_client.list_series_books(series_id)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Series {series_id} not found"
            )

        from datetime import datetime
        result["cached"] = False  # TODO: Detect cache hit
        result["timestamp"] = datetime.utcnow().isoformat() + "Z"

        logger.info(f"✅ Returned {len(result.get('books', []))} books for series '{result.get('series_name')}'")
        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fetch series books: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch series books: {str(e)}"
        )


@router.get("/api/series/health")
async def series_health():
    """
    Check Hardcover API configuration and connectivity.

    Response:
        {
            "configured": true,
            "status": "ok",
            "message": "Hardcover API is configured and ready"
        }
    """
    if not hardcover_client.is_configured:
        return JSONResponse({
            "configured": False,
            "status": "not_configured",
            "message": "HARDCOVER_API_TOKEN not set"
        })

    # TODO: Add actual connectivity test if needed
    return JSONResponse({
        "configured": True,
        "status": "ok",
        "message": "Hardcover API is configured and ready"
    })
