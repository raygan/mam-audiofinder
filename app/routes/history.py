"""
History routes for MAM Audiobook Finder.
"""
import httpx
from fastapi import APIRouter
from sqlalchemy import text

from db import engine
from qb_client import qb_login_sync
from torrent_helpers import (
    get_torrent_state,
    map_qb_state_to_display,
    validate_torrent_path
)

router = APIRouter()


@router.get("/history")
def history():
    """Get history of added torrents with live torrent states."""
    # Fetch all history items
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT id, mam_id, title, author, narrator, dl, qb_hash, added_at, qb_status,
                   abs_cover_url, abs_item_id
            FROM history
            ORDER BY id DESC
            LIMIT 200
        """)).mappings().all()

    items = []

    # Enrich with live torrent data
    with httpx.Client(timeout=30) as client:
        try:
            qb_login_sync(client)
        except Exception as e:
            # If qBittorrent is unreachable, return basic data without enrichment
            import logging
            logger = logging.getLogger("mam-audiofinder")
            logger.error(f"qBittorrent login failed in /history: {e}")

            # Return rows with default status indicators
            enriched_items = []
            for row in rows:
                item = dict(row)
                item["qb_status"] = item.get("qb_status") or "qBittorrent Offline"
                item["qb_status_color"] = "red"
                item["qb_progress"] = 0.0
                item["path_warning"] = "Cannot connect to qBittorrent to verify status"
                item["path_valid"] = False
                enriched_items.append(item)

            return {"items": enriched_items}

        for row in rows:
            item = dict(row)
            qb_hash = item.get("qb_hash")

            # Default values
            item["qb_status_color"] = "grey"
            item["qb_progress"] = 0.0
            item["path_warning"] = None
            item["path_valid"] = True

            if qb_hash:
                # Fetch live state
                torrent_state = get_torrent_state(qb_hash, client)

                if torrent_state:
                    # Map state to display format
                    display_state, color = map_qb_state_to_display(
                        torrent_state.get("state", ""),
                        torrent_state.get("progress", 0)
                    )
                    item["qb_status"] = display_state
                    item["qb_status_color"] = color
                    item["qb_progress"] = torrent_state.get("progress", 0)

                    # Validate path
                    path_validation = validate_torrent_path(
                        torrent_state.get("save_path", ""),
                        torrent_state.get("content_path", "")
                    )
                    item["path_valid"] = path_validation["is_valid"]
                    item["path_warning"] = path_validation["warning"]

                    # Override color to red if path is invalid
                    if not path_validation["is_valid"]:
                        item["qb_status_color"] = "red"
                else:
                    # Torrent not found in qBittorrent
                    item["qb_status"] = "Not Found"
                    item["qb_status_color"] = "grey"

            items.append(item)

    return {"items": items}


@router.delete("/history/{row_id}")
def delete_history(row_id: int):
    """Delete a history entry."""
    with engine.begin() as cx:
        cx.execute(text("DELETE FROM history WHERE id = :id"), {"id": row_id})
    return {"ok": True}
