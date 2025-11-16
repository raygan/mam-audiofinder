"""
Import routes for MAM Audiobook Finder.
"""
import json
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
from abs_client import abs_client

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


def read_metadata_json(directory: Path) -> dict:
    """
    Read metadata.json from the imported directory.
    Returns dict with title, authors, narrators, series, etc. or empty dict if not found.
    """
    metadata_path = directory / "metadata.json"

    if not metadata_path.exists():
        logger.info(f"No metadata.json found in {directory}")
        return {}

    try:
        logger.info(f"📖 Reading metadata.json from {metadata_path}")
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        # Extract relevant fields
        result = {
            "title": metadata.get("title", ""),
            "subtitle": metadata.get("subtitle", ""),
            "authors": metadata.get("authors", []),  # List of author names
            "narrators": metadata.get("narrators", []),  # List of narrator names
            "series": metadata.get("series", []),  # List like ["Series Name #1"]
            "publisher": metadata.get("publisher", ""),
            "description": metadata.get("description", ""),
            "asin": metadata.get("asin", ""),
            "isbn": metadata.get("isbn", ""),
            "publishedYear": metadata.get("publishedYear", ""),
        }

        logger.info(f"📚 Metadata found: title='{result['title']}', authors={result['authors']}, narrators={result['narrators']}")
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"⚠️  Failed to parse metadata.json: {e}")
        return {}
    except Exception as e:
        logger.warning(f"⚠️  Error reading metadata.json: {e}")
        return {}


class ImportBody(BaseModel):
    """Request body for importing torrent."""
    author: str
    title: str
    hash: str
    history_id: int | None = None
    flatten: bool | None = None  # If None, uses global FLATTEN_DISCS setting


@router.post("/import")
async def do_import(body: ImportBody):
    """Import completed torrent to library."""
    author = sanitize(body.author)
    title = sanitize(body.title)
    h = body.hash

    # Use per-request flatten setting, fallback to global FLATTEN_DISCS
    use_flatten = body.flatten if body.flatten is not None else FLATTEN_DISCS

    # Query qB for files, properties, and content_path
    with httpx.Client(timeout=30) as c:
        # login
        qb_login_sync(c)

        # files (used to detect single-file)
        fr = c.get(f"{QB_URL}/api/v2/torrents/files", params={"hash": h})
        if fr.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"[QB-001] Cannot connect to qBittorrent\n"
                    f"API endpoint: {QB_URL}/api/v2/torrents/files\n"
                    f"Status code: {fr.status_code}\n"
                    f"See: https://github.com/magrhino/mam-audiofinder/blob/main/ERRORS.md#qb-001-cannot-connect-to-qbittorrent"
                )
            )
        files = fr.json()
        if not files:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"[IMPORT-002] No files found for torrent\n"
                    f"Torrent hash: {h}\n"
                    f"The torrent may not exist or may have been removed."
                )
            )

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
            raise HTTPException(
                status_code=404,
                detail=(
                    f"[IMPORT-003] Torrent content path not found\n"
                    f"Torrent hash: {h}\n"
                    f"qBittorrent may not have metadata for this torrent."
                )
            )

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
            detail=(
                f"[PATH-MISMATCH-001] Source path not found\n"
                f"Container path: {src_root}\n"
                f"qBittorrent reports: {content_path}\n"
                f"See: https://github.com/magrhino/mam-audiofinder/blob/main/ERRORS.md#path-mismatch-001-source-path-not-found"
            )
        )

    # Destination: /library/Author/Title[/...]
    lib = Path(LIB_DIR)
    author_dir = lib / author
    try:
        author_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=(
                f"[PATH-MISMATCH-002] Cannot write to library directory\n"
                f"Directory: {author_dir}\n"
                f"Error: {str(e)}\n"
                f"See: https://github.com/magrhino/mam-audiofinder/blob/main/ERRORS.md#path-mismatch-002-lib_dir-not-accessible"
            )
        )
    dest_dir = next_available(author_dir / title)

    # Copy/link all (skip .cue) and count files
    files_copied = 0
    files_linked = 0
    files_moved = 0
    if src_root.is_file():
        if src_root.suffix.lower() == ".cue":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"[IMPORT-001] No audio files found to import\n"
                    f"Only .cue file found: {src_root.name}\n"
                    f"See: https://github.com/magrhino/mam-audiofinder/blob/main/ERRORS.md#import-001-no-audio-files-found"
                )
            )
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

        # If flatten is enabled, sort by disc/track and rename sequentially
        if use_flatten and audio_files:
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
            detail=(
                f"[IMPORT-001] No audio files found to import\n"
                f"Directory: {src_root}\n"
                f"Found only .cue files or directory is empty.\n"
                f"See: https://github.com/magrhino/mam-audiofinder/blob/main/ERRORS.md#import-001-no-audio-files-found"
            )
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

    # --- Read metadata.json if available ---
    metadata = read_metadata_json(dest_dir)

    # --- Verify import in Audiobookshelf ---
    # Don't fail the import if verification fails, just log it
    verification_result = None
    try:
        # Use metadata.json if available, otherwise use torrent metadata
        verify_title = metadata.get("title", title) if metadata else title
        verify_authors = metadata.get("authors", [author]) if metadata else [author]
        verify_author = ", ".join(verify_authors) if verify_authors else author

        logger.info(f"🔍 Starting ABS verification for '{verify_title}' by '{verify_author}'")
        if metadata:
            logger.info(f"📖 Using metadata.json for verification (more accurate)")

        verification_result = await abs_client.verify_import(
            title=verify_title,
            author=verify_author,
            library_path=str(dest_dir),
            metadata=metadata  # Pass full metadata for enhanced matching
        )

        # Update database with verification results
        with engine.begin() as cx:
            if body.history_id is not None:
                cx.execute(
                    text("""
                        UPDATE history
                        SET abs_verify_status=:status, abs_verify_note=:note
                        WHERE id=:id
                    """),
                    {
                        "status": verification_result.get("status"),
                        "note": verification_result.get("note"),
                        "id": body.history_id
                    }
                )
            else:
                # Fallback: try by torrent hash
                cx.execute(
                    text("""
                        UPDATE history
                        SET abs_verify_status=:status, abs_verify_note=:note
                        WHERE qb_hash=:h
                    """),
                    {
                        "status": verification_result.get("status"),
                        "note": verification_result.get("note"),
                        "h": body.hash
                    }
                )

        # Log verification outcome
        status = verification_result.get("status", "unknown")
        note = verification_result.get("note", "")
        if status == "verified":
            logger.info(f"✅ Import verification successful: {note}")
        elif status == "mismatch":
            logger.warning(f"⚠️  Import verification mismatch: {note}")
        elif status == "not_found":
            logger.warning(f"⚠️  Import not found in ABS: {note}")
        elif status in ("unreachable", "not_configured"):
            logger.info(f"ℹ️  Import verification skipped: {note}")
        else:
            logger.warning(f"⚠️  Import verification unknown status '{status}': {note}")

    except Exception as e:
        # Log error but don't fail the import
        logger.error(f"❌ Import verification failed with exception: {type(e).__name__}: {e}")
        # Try to update database with error status
        try:
            with engine.begin() as cx:
                if body.history_id is not None:
                    cx.execute(
                        text("""
                            UPDATE history
                            SET abs_verify_status='unreachable',
                                abs_verify_note=:note
                            WHERE id=:id
                        """),
                        {
                            "note": f"Verification error: {type(e).__name__}",
                            "id": body.history_id
                        }
                    )
                else:
                    cx.execute(
                        text("""
                            UPDATE history
                            SET abs_verify_status='unreachable',
                                abs_verify_note=:note
                            WHERE qb_hash=:h
                        """),
                        {
                            "note": f"Verification error: {type(e).__name__}",
                            "h": body.hash
                        }
                    )
        except Exception:
            # If even the error update fails, just pass
            pass

    return {
        "ok": True,
        "dest": str(dest_dir),
        "files_copied": files_copied,
        "files_linked": files_linked,
        "files_moved": files_moved,
        "import_mode": IMPORT_MODE,
        "flatten_applied": use_flatten,
        "verification": verification_result if verification_result else {"status": "not_attempted"}
    }
