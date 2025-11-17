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

    Cleans up common metadata issues:
    - Removes disc indicators from titles (e.g., "(Disc 01)")
    - Cleans author names (removes " - translator", " - contributor", etc.)
    - Handles multiple authors properly
    """
    metadata_path = directory / "metadata.json"

    if not metadata_path.exists():
        logger.info(f"No metadata.json found in {directory}")
        return {}

    try:
        logger.info(f"📖 Reading metadata.json from {metadata_path}")
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        # Extract and clean title - remove disc indicators
        import re
        raw_title = metadata.get("title", "")
        clean_title = re.sub(r'\s*\(Disc\s+\d+\)\s*$', '', raw_title, flags=re.IGNORECASE)
        clean_title = re.sub(r'\s*\(Disk\s+\d+\)\s*$', '', clean_title, flags=re.IGNORECASE)
        clean_title = re.sub(r'\s*\(CD\s+\d+\)\s*$', '', clean_title, flags=re.IGNORECASE)
        clean_title = clean_title.strip()

        # Clean authors - remove role indicators
        raw_authors = metadata.get("authors", [])
        clean_authors = []
        for author in raw_authors:
            if isinstance(author, str):
                # Remove role indicators like "- translator", "- contributor", etc.
                clean_author = re.sub(r'\s*-\s*(translator|contributor|editor|foreword|introduction|afterword).*$', '', author, flags=re.IGNORECASE)
                clean_author = clean_author.strip()
                if clean_author:
                    clean_authors.append(clean_author)

        # Extract relevant fields
        result = {
            "title": clean_title or raw_title,  # Fallback to raw if cleaning removed everything
            "subtitle": metadata.get("subtitle", ""),
            "authors": clean_authors if clean_authors else raw_authors,  # Use cleaned or original
            "narrators": metadata.get("narrators", []),  # List of narrator names
            "series": metadata.get("series", []),  # List like ["Series Name #1"]
            "publisher": metadata.get("publisher", ""),
            "description": metadata.get("description", ""),
            "asin": metadata.get("asin", ""),
            "isbn": metadata.get("isbn", ""),
            "publishedYear": metadata.get("publishedYear", ""),
        }

        logger.info(f"📚 Metadata found: title='{result['title']}', authors={result['authors']}, narrators={result['narrators']}")
        if raw_title != clean_title:
            logger.info(f"   🧹 Cleaned title: '{raw_title}' → '{clean_title}'")
        if raw_authors != clean_authors:
            logger.info(f"   🧹 Cleaned authors: {raw_authors} → {clean_authors}")

        return result

    except json.JSONDecodeError as e:
        logger.warning(f"⚠️  Failed to parse metadata.json: {e}")
        return {}
    except Exception as e:
        logger.warning(f"⚠️  Error reading metadata.json: {e}")
        return {}


def insert_torrent_book(
    torrent_hash: str,
    history_id: int,
    book_title: str,
    book_author: str,
    position: int | None,
    subdirectory: str,
    series_name: str | None,
    abs_item_id: str | None = None,
    abs_verify_status: str | None = None,
    abs_verify_note: str | None = None,
) -> int:
    """
    Insert a torrent_books record linking a torrent to a book.
    Returns: torrent_book_id (primary key of inserted row)
    """
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO torrent_books (
                    torrent_hash, history_id, position, subdirectory,
                    book_title, book_author, series_name,
                    imported_at, abs_item_id, abs_verify_status, abs_verify_note
                ) VALUES (
                    :torrent_hash, :history_id, :position, :subdirectory,
                    :book_title, :book_author, :series_name,
                    datetime('now'), :abs_item_id, :abs_verify_status, :abs_verify_note
                )
            """),
            {
                "torrent_hash": torrent_hash,
                "history_id": history_id,
                "position": position,
                "subdirectory": subdirectory,
                "book_title": book_title,
                "book_author": book_author,
                "series_name": series_name,
                "abs_item_id": abs_item_id,
                "abs_verify_status": abs_verify_status,
                "abs_verify_note": abs_verify_note,
            }
        )
        return result.lastrowid


class ImportBody(BaseModel):
    """Request body for importing torrent."""
    author: str
    title: str
    hash: str
    history_id: int | None = None
    flatten: bool | None = None  # If None, uses global FLATTEN_DISCS setting


class BookPayload(BaseModel):
    """Single book within a multi-book torrent."""
    title: str
    author: str
    subdirectory: str  # Relative path within torrent root (e.g., "Book 1 - Title")
    position: int | None = None  # Book position in series (optional)
    series_name: str | None = None  # Series name if applicable


class MultiBookImportBody(BaseModel):
    """Request body for importing multiple books from single torrent."""
    torrent_hash: str
    history_id: int  # Primary history entry for the torrent
    books: list[BookPayload]  # List of books to import
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

    # --- Read metadata.json if available (with retry for ABS scan) ---
    # Wait for Audiobookshelf to scan the imported files and create metadata.json
    import asyncio
    metadata = {}
    max_wait_attempts = 6  # 6 attempts = ~30 seconds total
    for attempt in range(1, max_wait_attempts + 1):
        metadata = read_metadata_json(dest_dir)
        if metadata:
            logger.info(f"📖 Found metadata.json on attempt {attempt}")
            break
        elif attempt < max_wait_attempts:
            wait_time = 5  # Wait 5 seconds between checks
            logger.info(f"⏳ Waiting {wait_time}s for metadata.json (attempt {attempt}/{max_wait_attempts})")
            await asyncio.sleep(wait_time)
        else:
            logger.info(f"ℹ️  No metadata.json found after {max_wait_attempts} attempts, proceeding with torrent metadata")

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


@router.post("/import/multi-book")
async def do_multi_book_import(body: MultiBookImportBody):
    """
    Import multiple books from a single torrent to library.

    Each book is imported to a separate directory and verified individually.
    Disc flattening is applied per book, preserving the helper contracts.
    """
    import asyncio

    torrent_hash = body.torrent_hash
    use_flatten = body.flatten if body.flatten is not None else FLATTEN_DISCS

    # Query qBittorrent for torrent information
    with httpx.Client(timeout=30) as c:
        qb_login_sync(c)

        # Get torrent info to find content_path (torrent root directory)
        ir = c.get(f"{QB_URL}/api/v2/torrents/info", params={"hashes": torrent_hash})
        if ir.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"[QB-001] Cannot connect to qBittorrent\n"
                    f"API endpoint: {QB_URL}/api/v2/torrents/info\n"
                    f"Status code: {ir.status_code}\n"
                    f"See: https://github.com/magrhino/mam-audiofinder/blob/main/ERRORS.md#qb-001-cannot-connect-to-qbittorrent"
                )
            )

        info_list = ir.json()
        if not isinstance(info_list, list) or not info_list:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"[IMPORT-003] Torrent not found\n"
                    f"Torrent hash: {torrent_hash}\n"
                    f"The torrent may have been removed from qBittorrent."
                )
            )

        info = info_list[0]
        content_path = info.get("content_path") or ""
        if not content_path:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"[IMPORT-003] Torrent content path not found\n"
                    f"Torrent hash: {torrent_hash}\n"
                    f"qBittorrent may not have metadata for this torrent."
                )
            )

    # Map qB's internal paths to this container's paths
    def map_qb_path(p: str) -> str:
        prefix = QB_INNER_DL_PREFIX.rstrip("/")
        if p == prefix or p.startswith(prefix + "/"):
            return p.replace(QB_INNER_DL_PREFIX, DL_DIR, 1)
        if p.startswith("/media/"):
            return p
        p = p.replace("/mnt/user/media", "/media", 1)
        p = p.replace("/mnt/media", "/media", 1)
        return p

    torrent_root = Path(map_qb_path(content_path))

    # Validate torrent root exists
    if not torrent_root.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"[PATH-MISMATCH-001] Torrent root path not found\n"
                f"Container path: {torrent_root}\n"
                f"qBittorrent reports: {content_path}\n"
                f"See: https://github.com/magrhino/mam-audiofinder/blob/main/ERRORS.md#path-mismatch-001-source-path-not-found"
            )
        )

    # Process each book
    results = []
    total_files_copied = 0
    total_files_linked = 0
    total_files_moved = 0

    for book in body.books:
        book_result = {
            "book_title": book.title,
            "book_author": book.author,
            "subdirectory": book.subdirectory,
            "position": book.position,
            "ok": False,
            "error": None,
            "dest": None,
            "files_copied": 0,
            "files_linked": 0,
            "files_moved": 0,
            "verification": {"status": "not_attempted"},
            "abs_item_id": None,
        }

        try:
            # Sanitize book metadata
            author = sanitize(book.author)
            title = sanitize(book.title)

            # Source: torrent_root / subdirectory
            src_root = torrent_root / book.subdirectory

            if not src_root.exists():
                book_result["error"] = f"Subdirectory not found: {book.subdirectory}"
                results.append(book_result)
                logger.warning(f"⚠️  Book subdirectory not found: {src_root}")
                continue

            # Destination: /library/Author/Title
            lib = Path(LIB_DIR)
            author_dir = lib / author
            try:
                author_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                book_result["error"] = f"Cannot create author directory: {str(e)}"
                results.append(book_result)
                logger.error(f"❌ Cannot create author directory {author_dir}: {e}")
                continue

            dest_dir = next_available(author_dir / title)
            book_result["dest"] = str(dest_dir)

            # Copy/link files with disc flattening PER BOOK
            files_copied = 0
            files_linked = 0
            files_moved = 0

            if src_root.is_file():
                # Single file case
                if src_root.suffix.lower() != ".cue":
                    action = copy_one(src_root, dest_dir / src_root.name)
                    files_copied = 1
                    if action == "linked":
                        files_linked = 1
                    elif action == "moved":
                        files_moved = 1
            else:
                # Directory case: collect audio files
                audio_files = []
                for p in src_root.rglob("*"):
                    if not p.is_file():
                        continue
                    if p.suffix.lower() == ".cue":
                        continue
                    audio_files.append(p)

                # Apply disc flattening WITHIN this book's directory
                if use_flatten and audio_files:
                    files_with_info = []
                    for p in audio_files:
                        disc_num, track_num, ext = extract_disc_track(p, src_root)
                        files_with_info.append((disc_num, track_num, ext, p))

                    # Sort by disc, then track
                    files_with_info.sort(key=lambda x: (x[0], x[1]))

                    # Copy with sequential naming (preserves flattening contract)
                    for idx, (disc_num, track_num, ext, src_path) in enumerate(files_with_info, start=1):
                        new_name = f"Part {idx:03d}{ext}"
                        action = copy_one(src_path, dest_dir / new_name)
                        files_copied += 1
                        if action == "linked":
                            files_linked += 1
                        elif action == "moved":
                            files_moved += 1
                else:
                    # Preserve directory structure
                    for p in audio_files:
                        rel = p.relative_to(src_root)
                        action = copy_one(p, dest_dir / rel)
                        files_copied += 1
                        if action == "linked":
                            files_linked += 1
                        elif action == "moved":
                            files_moved += 1

            if files_copied == 0:
                book_result["error"] = "No audio files found in subdirectory"
                results.append(book_result)
                logger.warning(f"⚠️  No audio files found in {src_root}")
                continue

            book_result["files_copied"] = files_copied
            book_result["files_linked"] = files_linked
            book_result["files_moved"] = files_moved
            total_files_copied += files_copied
            total_files_linked += files_linked
            total_files_moved += files_moved

            # Wait for metadata.json (ABS scan)
            metadata = {}
            max_wait_attempts = 6
            for attempt in range(1, max_wait_attempts + 1):
                metadata = read_metadata_json(dest_dir)
                if metadata:
                    logger.info(f"📖 Found metadata.json for '{title}' on attempt {attempt}")
                    break
                elif attempt < max_wait_attempts:
                    wait_time = 5
                    logger.info(f"⏳ Waiting {wait_time}s for metadata.json for '{title}' (attempt {attempt}/{max_wait_attempts})")
                    await asyncio.sleep(wait_time)
                else:
                    logger.info(f"ℹ️  No metadata.json for '{title}' after {max_wait_attempts} attempts")

            # Verify in Audiobookshelf (per book)
            verification_result = None
            abs_item_id = None
            abs_verify_status = None
            abs_verify_note = None

            try:
                verify_title = metadata.get("title", title) if metadata else title
                verify_authors = metadata.get("authors", [author]) if metadata else [author]
                verify_author = ", ".join(verify_authors) if verify_authors else author

                logger.info(f"🔍 Starting ABS verification for '{verify_title}' by '{verify_author}'")

                verification_result = await abs_client.verify_import(
                    title=verify_title,
                    author=verify_author,
                    library_path=str(dest_dir),
                    metadata=metadata
                )

                abs_verify_status = verification_result.get("status")
                abs_verify_note = verification_result.get("note")
                abs_item_id = verification_result.get("abs_item_id")

                book_result["verification"] = verification_result
                book_result["abs_item_id"] = abs_item_id

                # Log verification outcome
                status = abs_verify_status or "unknown"
                if status == "verified":
                    logger.info(f"✅ Verification successful for '{title}': {abs_verify_note}")
                elif status == "mismatch":
                    logger.warning(f"⚠️  Verification mismatch for '{title}': {abs_verify_note}")
                elif status == "not_found":
                    logger.warning(f"⚠️  Not found in ABS for '{title}': {abs_verify_note}")
                else:
                    logger.info(f"ℹ️  Verification status '{status}' for '{title}': {abs_verify_note}")

            except Exception as e:
                logger.error(f"❌ Verification failed for '{title}': {type(e).__name__}: {e}")
                abs_verify_status = "unreachable"
                abs_verify_note = f"Verification error: {type(e).__name__}"
                book_result["verification"] = {"status": abs_verify_status, "note": abs_verify_note}

            # Insert torrent_books record
            try:
                torrent_book_id = insert_torrent_book(
                    torrent_hash=torrent_hash,
                    history_id=body.history_id,
                    book_title=book.title,
                    book_author=book.author,
                    position=book.position,
                    subdirectory=book.subdirectory,
                    series_name=book.series_name,
                    abs_item_id=abs_item_id,
                    abs_verify_status=abs_verify_status,
                    abs_verify_note=abs_verify_note,
                )
                logger.info(f"📝 Created torrent_books record #{torrent_book_id} for '{title}'")
            except Exception as e:
                logger.error(f"❌ Failed to insert torrent_books record for '{title}': {e}")
                # Don't fail the import, just log

            book_result["ok"] = True
            results.append(book_result)
            logger.info(f"✅ Successfully imported book '{title}' by '{author}'")

        except Exception as e:
            logger.error(f"❌ Failed to import book '{book.title}': {type(e).__name__}: {e}")
            book_result["error"] = f"{type(e).__name__}: {str(e)}"
            results.append(book_result)

    # Update primary history entry with overall status
    try:
        with engine.begin() as cx:
            cx.execute(
                text("UPDATE history SET qb_status='imported', imported_at=:ts WHERE id=:id"),
                {"ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), "id": body.history_id},
            )
    except Exception as e:
        logger.error(f"❌ Failed to update history entry #{body.history_id}: {e}")

    # Post-import: change qB category (best effort)
    if torrent_hash and QB_URL:
        try:
            with httpx.Client(timeout=15) as c2:
                qb_login_sync(c2)
                c2.post(
                    f"{QB_URL}/api/v2/torrents/setCategory",
                    data={"hashes": torrent_hash, "category": QB_POSTIMPORT_CATEGORY},
                )
        except Exception:
            pass

    # Calculate success/failure counts
    success_count = sum(1 for r in results if r["ok"])
    failure_count = len(results) - success_count

    return {
        "ok": True,
        "torrent_hash": torrent_hash,
        "history_id": body.history_id,
        "books_processed": len(results),
        "books_succeeded": success_count,
        "books_failed": failure_count,
        "total_files_copied": total_files_copied,
        "total_files_linked": total_files_linked,
        "total_files_moved": total_files_moved,
        "import_mode": IMPORT_MODE,
        "flatten_applied": use_flatten,
        "results": results,
    }
