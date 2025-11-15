"""
Import routes for MAM Audiobook Finder.
"""
import logging
import shutil
import httpx
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from config import (
    DL_DIR, LIB_DIR, IMPORT_MODE, FLATTEN_DISCS, AUDIO_EXTS,
    QB_URL, QB_INNER_DL_PREFIX, QB_POSTIMPORT_CATEGORY
)
from db import engine
from qb_client import qb_login_sync
from utils import sanitize, next_available, extract_disc_track, try_hardlink

router = APIRouter()
logger = logging.getLogger("mam-audiofinder")


def copy_one(src: Path, dst: Path) -> str:
    """
    Copy/link/move a file based on IMPORT_MODE.
    Returns: "linked", "copied", or "moved"
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if IMPORT_MODE == "move":
        shutil.move(src, dst)
        return "moved"
    elif IMPORT_MODE == "link":
        if try_hardlink(src, dst):
            return "linked"
        else:
            shutil.copy2(src, dst)
            return "copied"
    else:  # copy
        shutil.copy2(src, dst)
        return "copied"


class ImportBody(BaseModel):
    """Request body for importing torrent."""
    author: str
    title: str
    hash: str
    history_id: int | None = None


@router.post("/import")
def do_import(body: ImportBody):
    """Import completed torrent to library."""
    author = sanitize(body.author)
    title = sanitize(body.title)
    h = body.hash

    # Query qB for files, properties, and content_path
    with httpx.Client(timeout=30) as c:
        # login
        qb_login_sync(c)

        # files (used to detect single-file)
        fr = c.get(f"{QB_URL}/api/v2/torrents/files", params={"hash": h})
        if fr.status_code != 200:
            raise HTTPException(status_code=502, detail=f"qB files failed: {fr.status_code}")
        files = fr.json()
        if not files:
            raise HTTPException(status_code=404, detail="No files found for torrent")

        # properties (optional save_path)
        pr = c.get(f"{QB_URL}/api/v2/torrents/properties", params={"hash": h})
        save_path = ""
        if pr.status_code == 200:
            save_path = (pr.json().get("save_path") or "").rstrip("/")

        # info (to get content_path)
        ir = c.get(f"{QB_URL}/api/v2/torrents/info", params={"hashes": h})
        info_list = ir.json() if ir.status_code == 200 else []
        info = info_list[0] if isinstance(info_list, list) and info_list else {}
        content_path = info.get("content_path") or ""
        if not content_path:
            raise HTTPException(status_code=404, detail="Torrent content path not found")

    # map qB's internal paths to this container's paths
    def map_qb_path(p: str) -> str:
        prefix = QB_INNER_DL_PREFIX.rstrip("/")
        if p == prefix or p.startswith(prefix + "/"):
            return p.replace(QB_INNER_DL_PREFIX, DL_DIR, 1)
        if p.startswith("/media/"):
            return p
        p = p.replace("/mnt/user/media", "/media", 1)
        p = p.replace("/mnt/media", "/media", 1)
        return p

    src_root = Path(map_qb_path(content_path))

    # Validate source path exists
    if not src_root.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Source path not found: {src_root}. content_path from qB: {content_path}"
        )

    # Destination: /library/Author/Title[/...]
    lib = Path(LIB_DIR)
    author_dir = lib / author
    author_dir.mkdir(parents=True, exist_ok=True)
    dest_dir = next_available(author_dir / title)

    # Copy/link all (skip .cue) and count files
    files_copied = 0
    files_linked = 0
    files_moved = 0
    if src_root.is_file():
        if src_root.suffix.lower() == ".cue":
            raise HTTPException(status_code=400, detail="Only .cue file found; nothing to import")
        action = copy_one(src_root, dest_dir / src_root.name)
        files_copied = 1
        if action == "linked":
            files_linked = 1
        elif action == "moved":
            files_moved = 1
    else:
        # Collect all audio files
        audio_files = []
        for p in src_root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() == ".cue":
                continue
            audio_files.append(p)

        # If FLATTEN_DISCS is enabled, sort by disc/track and rename sequentially
        if FLATTEN_DISCS and audio_files:
            # Extract disc/track info and sort
            files_with_info = []
            for p in audio_files:
                disc_num, track_num, ext = extract_disc_track(p, src_root)
                files_with_info.append((disc_num, track_num, ext, p))

            # Sort by disc number, then track number
            files_with_info.sort(key=lambda x: (x[0], x[1]))

            # Determine if this is a multi-disc structure
            has_discs = any(disc_num > 0 for disc_num, _, _, _ in files_with_info)

            # Copy with sequential naming
            for idx, (disc_num, track_num, ext, src_path) in enumerate(files_with_info, start=1):
                # Generate new filename: Part 001.mp3, Part 002.mp3, etc.
                new_name = f"Part {idx:03d}{ext}"
                action = copy_one(src_path, dest_dir / new_name)
                files_copied += 1
                if action == "linked":
                    files_linked += 1
                elif action == "moved":
                    files_moved += 1
        else:
            # Original behavior: preserve directory structure
            for p in audio_files:
                rel = p.relative_to(src_root)
                action = copy_one(p, dest_dir / rel)
                files_copied += 1
                if action == "linked":
                    files_linked += 1
                elif action == "moved":
                    files_moved += 1

    # Validate that we actually copied something
    if files_copied == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No audio files found to import in {src_root}. Found only .cue files or directory is empty."
        )

    # --- post-import: clear or change category so it disappears from our list ---
    if h and QB_URL:
        try:
            with httpx.Client(timeout=15) as c2:
                qb_login_sync(c2)
                # Setting to empty string unsets the category on most qB versions.
                # If your qB requires an existing category, set QB_POSTIMPORT_CATEGORY to that name.
                c2.post(
                    f"{QB_URL}/api/v2/torrents/setCategory",
                    data={"hashes": h, "category": QB_POSTIMPORT_CATEGORY},
                )
        except Exception as _e:
            # Best effort: don't fail the import if this errors.
            pass

    # --- mark history as imported ---
    with engine.begin() as cx:
        if body.history_id is not None:
            cx.execute(
                text("UPDATE history SET qb_status='imported', imported_at=:ts WHERE id=:id"),
                {"ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), "id": body.history_id},
            )
        else:
            # Fallback: try by torrent hash if we have it
            cx.execute(
                text("UPDATE history SET qb_status='imported', imported_at=:ts WHERE qb_hash=:h"),
                {"ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), "h": body.hash},
            )

    return {
        "ok": True,
        "dest": str(dest_dir),
        "files_copied": files_copied,
        "files_linked": files_linked,
        "files_moved": files_moved,
        "import_mode": IMPORT_MODE,
    }
