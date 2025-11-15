"""
History routes for MAM Audiobook Finder.
"""
from fastapi import APIRouter
from sqlalchemy import text

from db import engine

router = APIRouter()


@router.get("/history")
def history():
    """Get history of added torrents."""
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT id, mam_id, title, author, narrator, dl, qb_hash, added_at, qb_status,
                   abs_cover_url, abs_item_id
            FROM history
            ORDER BY id DESC
            LIMIT 200
        """)).mappings().all()
    return {"items": list(rows)}


@router.delete("/history/{row_id}")
def delete_history(row_id: int):
    """Delete a history entry."""
    with engine.begin() as cx:
        cx.execute(text("DELETE FROM history WHERE id = :id"), {"id": row_id})
    return {"ok": True}
