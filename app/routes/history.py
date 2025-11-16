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
    validate_torrent_path,
    extract_mam_id_from_tags,
    match_torrent_to_history
)

router = APIRouter()


@router.get("/api/history")
def history():
    """Get history of added torrents with live torrent states."""
    import logging
    logger = logging.getLogger("mam-audiofinder")
    logger.info("[HISTORY] /api/history endpoint called")

    # Fetch all history items
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT id, mam_id, title, author, narrator, dl, qb_hash, added_at, qb_status,
                   abs_cover_url, abs_item_id, imported_at,
                   abs_verify_status, abs_verify_note
            FROM history
            ORDER BY id DESC
            LIMIT 200
        """)).mappings().all()

    logger.info(f"[HISTORY] Found {len(rows)} history items in database")
    items = []

    # Enrich with live torrent data
    with httpx.Client(timeout=30) as client:
        try:
            qb_login_sync(client)
            logger.info("[HISTORY] Successfully logged into qBittorrent")
        except Exception as e:
            # If qBittorrent is unreachable, return basic data without enrichment
            logger.error(f"[HISTORY] qBittorrent login failed in /history: {e}")

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

        # Fetch ALL torrents once for matching
        logger.info("[HISTORY] Fetching all torrents from qBittorrent for matching")
        try:
            from config import QB_URL
            torrents_resp = client.get(f"{QB_URL}/api/v2/torrents/info", params={"filter": "all"})
            all_torrents = []
            if torrents_resp.status_code == 200:
                qb_torrents = torrents_resp.json()
                if isinstance(qb_torrents, list):
                    # Extract mam_id from tags for each torrent
                    for t in qb_torrents:
                        torrent_data = {
                            "hash": t.get("hash"),
                            "name": t.get("name"),
                            "tags": t.get("tags", ""),
                            "mam_id": extract_mam_id_from_tags(t.get("tags", ""))
                        }
                        all_torrents.append(torrent_data)
                    logger.info(f"[HISTORY] Fetched {len(all_torrents)} torrents from qBittorrent")
        except Exception as e:
            logger.error(f"[HISTORY] Failed to fetch torrent list: {e}")
            all_torrents = []

        for row in rows:
            item = dict(row)
            qb_hash = item.get("qb_hash")
            hash_updated = False

            # Default values
            item["qb_status_color"] = "grey"
            item["qb_progress"] = 0.0
            item["path_warning"] = None
            item["path_valid"] = True

            # If no hash, try to find matching torrent
            if not qb_hash and all_torrents:
                logger.info(f"[HISTORY] No hash for '{item.get('title')}', attempting fallback match")
                matched_torrent = match_torrent_to_history(item, all_torrents)
                if matched_torrent:
                    qb_hash = matched_torrent.get("hash")
                    logger.info(f"[HISTORY] Matched by {'MAM ID' if matched_torrent.get('mam_id') else 'title'}: {qb_hash}")

                    # Update database with found hash for future lookups
                    try:
                        with engine.begin() as cx:
                            cx.execute(text("""
                                UPDATE history
                                SET qb_hash = :qb_hash
                                WHERE id = :id
                            """), {"qb_hash": qb_hash, "id": item.get("id")})
                        logger.info(f"[HISTORY] Updated database with hash for item {item.get('id')}")
                        hash_updated = True
                    except Exception as e:
                        logger.error(f"[HISTORY] Failed to update hash in database: {e}")
                else:
                    logger.info(f"[HISTORY] No matching torrent found for '{item.get('title')}'")

            if qb_hash:
                logger.info(f"[HISTORY] Processing item with hash: {qb_hash}, title: {item.get('title')}{' (newly matched)' if hash_updated else ''}")
                # Fetch live state
                torrent_state = get_torrent_state(qb_hash, client)
                logger.info(f"[HISTORY] Torrent state for {qb_hash}: {torrent_state}")

                if torrent_state:
                    # Map state to display format
                    display_state, color = map_qb_state_to_display(
                        torrent_state.get("state", ""),
                        torrent_state.get("progress", 0)
                    )
                    logger.info(f"[HISTORY] Mapped state: {display_state}, color: {color}")
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
                        logger.info(f"[HISTORY] Path invalid for {qb_hash}, overriding color to red")
                else:
                    # Torrent not found in qBittorrent
                    logger.warning(f"[HISTORY] Torrent not found in qBittorrent: {qb_hash}")
                    item["qb_status"] = "Not Found"
                    item["qb_status_color"] = "grey"
            else:
                logger.info(f"[HISTORY] No hash available for: {item.get('title')}")

            items.append(item)

    logger.info(f"[HISTORY] Returning {len(items)} items with enriched data")
    if items:
        logger.info(f"[HISTORY] First item sample: title={items[0].get('title')}, qb_status={items[0].get('qb_status')}, qb_status_color={items[0].get('qb_status_color')}")

    return {"items": items}


@router.delete("/api/history/{row_id}")
def delete_history(row_id: int):
    """Delete a history entry."""
    with engine.begin() as cx:
        cx.execute(text("DELETE FROM history WHERE id = :id"), {"id": row_id})
    return {"ok": True}
