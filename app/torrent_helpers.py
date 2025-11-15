"""
Torrent state management helpers for MAM Audiobook Finder.
"""
import logging
import re
import httpx
from pathlib import Path
from typing import Any

from config import DL_DIR, QB_URL

logger = logging.getLogger("mam-audiofinder")


def map_qb_state_to_display(qb_state: str, progress: float) -> tuple[str, str]:
    """
    Convert qBittorrent state codes to user-friendly display.

    Returns: (display_text, color_code)
    Color codes: grey, blue, yellow, green, red
    """
    state_lower = (qb_state or "").lower()

    # Metadata fetch
    if state_lower in ["metadl", "fetchingmetadata"]:
        return "Fetching Metadata", "grey"

    # Downloading
    if state_lower in ["downloading", "downloadingmetadata", "forceddl", "stalleddl"]:
        if progress < 100:
            return f"Downloading ({progress:.1f}%)", "blue"
        else:
            return "Processing", "blue"

    # Moving files
    if state_lower in ["moving", "movingtostorage"]:
        return "Moving Files", "yellow"

    # Seeding / Ready
    if state_lower in ["uploading", "stalledup", "pausedup", "queuedup", "checkingresumedata"]:
        return "Seeding - Ready", "green"

    # Paused download
    if state_lower in ["pauseddl"]:
        return f"Paused ({progress:.1f}%)", "grey"

    # Checking
    if state_lower in ["checkingup", "checkingdl", "checkingresumedata"]:
        return "Checking Files", "yellow"

    # Error states
    if state_lower in ["error", "missingfiles", "unknown"]:
        return "Error", "red"

    # Unknown/fallback
    return qb_state or "Unknown", "grey"


def get_torrent_state(qb_hash: str, client: httpx.Client) -> dict[str, Any] | None:
    """
    Fetch live torrent info from qBittorrent.

    Returns: dict with state, progress, save_path, content_path, etc.
    Returns None if torrent not found or error occurs.
    """
    if not qb_hash:
        return None

    try:
        # Get basic info
        r = client.get(f"{QB_URL}/api/v2/torrents/info", params={"hashes": qb_hash})
        if r.status_code != 200:
            return None

        torrents = r.json()
        if not isinstance(torrents, list) or not torrents:
            return None

        torrent = torrents[0]

        # Get properties for content_path
        props_r = client.get(f"{QB_URL}/api/v2/torrents/properties", params={"hash": qb_hash})
        content_path = ""
        if props_r.status_code == 200:
            props = props_r.json()
            content_path = props.get("content_path", "")

        return {
            "hash": torrent.get("hash"),
            "name": torrent.get("name"),
            "state": torrent.get("state"),
            "progress": torrent.get("progress", 0) * 100,  # Convert to percentage
            "save_path": torrent.get("save_path", "").rstrip("/"),
            "content_path": content_path or torrent.get("content_path", ""),
            "size": torrent.get("total_size"),
            "category": torrent.get("category"),
            "tags": torrent.get("tags", ""),
        }
    except Exception as e:
        logger.error(f"Failed to fetch torrent state for {qb_hash}: {e}")
        return None


def validate_torrent_path(save_path: str, content_path: str) -> dict[str, Any]:
    """
    Check if torrent paths align with DL_DIR.

    Returns: {
        "is_valid": bool,
        "warning": str or None,
        "expected_path": str
    }
    """
    dl_dir_normalized = Path(DL_DIR).resolve()
    expected_prefix = str(dl_dir_normalized)

    # Check content_path first (more specific)
    check_path = content_path or save_path
    if not check_path:
        return {
            "is_valid": False,
            "warning": "Torrent path information not available",
            "expected_path": expected_prefix
        }

    try:
        # Resolve the path to handle symlinks
        actual_path = Path(check_path).resolve()

        # Check if it's under DL_DIR
        if dl_dir_normalized in actual_path.parents or actual_path == dl_dir_normalized:
            return {
                "is_valid": True,
                "warning": None,
                "expected_path": expected_prefix
            }
        else:
            return {
                "is_valid": False,
                "warning": f"Torrent in {check_path} but expected under {expected_prefix}",
                "expected_path": expected_prefix
            }
    except Exception as e:
        logger.warning(f"Path validation failed for {check_path}: {e}")
        return {
            "is_valid": False,
            "warning": f"Cannot validate path: {str(e)}",
            "expected_path": expected_prefix
        }


def extract_mam_id_from_tags(tags: str) -> str | None:
    """
    Extract MAM ID from qBittorrent tags string.
    Tags format: "tag1,tag2,mamid=12345,tag3"

    Returns: mam_id as string or None
    """
    if not tags:
        return None

    # Look for mamid=XXXXX pattern
    match = re.search(r'mamid=(\d+)', tags)
    if match:
        return match.group(1)

    return None


def match_torrent_to_history(history_item: dict, torrents: list[dict]) -> dict | None:
    """
    Find matching torrent for a history item.

    Matching priority:
    1. qb_hash (most reliable)
    2. mamid tag matching mam_id
    3. Fuzzy title match (fallback)

    Returns: matched torrent dict or None
    """
    if not torrents:
        return None

    history_hash = history_item.get("qb_hash")
    history_mam_id = str(history_item.get("mam_id") or "").strip()
    history_title = (history_item.get("title") or "").lower().strip()

    # Priority 1: Match by hash (most reliable)
    if history_hash:
        for torrent in torrents:
            if torrent.get("hash") == history_hash:
                return torrent

    # Priority 2: Match by mam_id from tags
    if history_mam_id:
        for torrent in torrents:
            torrent_mam_id = torrent.get("mam_id")
            if torrent_mam_id and str(torrent_mam_id) == history_mam_id:
                return torrent

    # Priority 3: Fuzzy title match (at least 80% of title matches)
    if history_title and len(history_title) > 10:
        best_match = None
        best_score = 0

        for torrent in torrents:
            torrent_name = (torrent.get("name") or "").lower().strip()

            # Simple substring matching
            # Check if first 20 chars of title appear in torrent name
            title_prefix = history_title[:20]
            if title_prefix in torrent_name:
                # Calculate rough match score
                score = len(title_prefix) / len(history_title)
                if score > best_score:
                    best_score = score
                    best_match = torrent

        if best_match and best_score > 0.5:  # At least 50% match
            return best_match

    return None
