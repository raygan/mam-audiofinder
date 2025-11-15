"""
Cover image serving routes for MAM Audiobook Finder.
"""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import COVERS_DIR

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
