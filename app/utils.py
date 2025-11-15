"""
Utility functions for MAM Audiobook Finder.
"""
import re
import os
import logging
from pathlib import Path

logger = logging.getLogger("mam-audiofinder")


def sanitize(name: str) -> str:
    """Sanitize filename for filesystem compatibility."""
    s = name.strip().replace(":", " -").replace("\\", "﹨").replace("/", "﹨")
    return re.sub(r"\s+", " ", s)[:200] or "Unknown"


def next_available(path: Path) -> Path:
    """Find next available path by appending (2), (3), etc."""
    if not path.exists():
        return path
    i = 2
    while True:
        cand = path.with_name(f"{path.name} ({i})")
        if not cand.exists():
            return cand
        i += 1


def extract_disc_track(path: Path, root: Path) -> tuple[int, int, str]:
    """
    Extract (disc_num, track_num, extension) from a file path.
    Returns (0, 0, ext) if no pattern detected.

    Patterns detected:
    - Directories: "Disc 01", "Disk 1", "CD 01", "Part 01", etc.
    - Files: "Track 01.mp3", "01.mp3", "Chapter 01.mp3", etc.
    """
    disc_num = 0
    track_num = 0
    ext = path.suffix

    # Get relative path components
    try:
        rel = path.relative_to(root)
    except ValueError:
        return (disc_num, track_num, ext)

    parts = rel.parts

    # Check directory names for disc number
    for part in parts[:-1]:  # All except filename
        # Match patterns like: "Disc 01", "Disk 1", "CD 01", "Part 01"
        m = re.search(r'(?:disc|disk|cd|part)\s*(\d+)', part, re.IGNORECASE)
        if m:
            disc_num = int(m.group(1))
            break

    # Check filename for track number
    filename = parts[-1] if parts else ""
    # Match patterns like: "Track 01.mp3", "01.mp3", "Chapter 01.mp3", "01 - Title.mp3"
    m = re.search(r'(?:track|chapter|^)[\s\-]*(\d+)', filename, re.IGNORECASE)
    if m:
        track_num = int(m.group(1))

    return (disc_num, track_num, ext)


def try_hardlink(src: Path, dst: Path) -> bool:
    """
    Try to create hardlink, return True on success.
    Logs detailed error information if linking fails.
    """
    try:
        # Get filesystem info for debugging
        src_stat = src.stat()
        src_dev = src_stat.st_dev

        # Get parent directory's filesystem (dst doesn't exist yet)
        dst_parent_dev = dst.parent.stat().st_dev

        # Check if they're on the same filesystem before attempting
        if src_dev != dst_parent_dev:
            logger.warning(
                f"Hardlink skipped (different filesystems): {src} -> {dst}. "
                f"Source device: {src_dev}, Dest parent device: {dst_parent_dev}. "
                f"Falling back to copy."
            )
            return False

        # Attempt the hardlink
        os.link(src, dst)
        logger.info(f"✓ Hardlinked: {src.name}")
        return True

    except OSError as e:
        logger.warning(
            f"Hardlink failed (falling back to copy): {src.name}. "
            f"Error: {e.errno} - {e.strerror}"
        )
        return False
    except Exception as e:
        logger.warning(
            f"Unexpected error during hardlink: {src.name}. "
            f"Error: {e.__class__.__name__}: {e}"
        )
        return False
