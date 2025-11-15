"""
Cover image serving routes for MAM Audiobook Finder.
"""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text

from config import COVERS_DIR
from abs_client import abs_client
from db import engine
from covers import cover_service

router = APIRouter()


@router.get("/covers/{filename}")
async def serve_cover(filename: str):
    """Serve cached cover images."""
    # Sanitize filename
    filename = Path(filename).name  # Remove any path traversal attempts
    filepath = COVERS_DIR / filename

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Cover not found")

    return FileResponse(filepath)


@router.post("/covers/refresh/{mam_id}")
async def refresh_cover(mam_id: str):
    """Force refresh of a cached cover for a specific MAM ID."""

    if not mam_id:
        raise HTTPException(status_code=400, detail="Missing MAM ID")

    if not abs_client.is_configured:
        raise HTTPException(status_code=400, detail="Audiobookshelf not configured")

    with engine.begin() as cx:
        row = cx.execute(text("""
            SELECT title, author FROM history
            WHERE mam_id = :mam_id
            ORDER BY id DESC
            LIMIT 1
        """), {"mam_id": mam_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="MAM ID not found in history")

    # Remove any stale cache entries/files before fetching again
    cover_service.invalidate_cover(mam_id)

    result = await abs_client.fetch_cover(row.title or "", row.author or "", mam_id, force_refresh=True)
    if not result or not result.get("cover_url"):
        raise HTTPException(status_code=404, detail="Unable to refresh cover")

    return {
        "mam_id": mam_id,
        "cover_url": result.get("cover_url"),
        "item_id": result.get("item_id")
    }
