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


def normalize_title(title: str) -> str:
    """
    Normalize book title for series search matching.

    Rules:
    - Convert to lowercase
    - Remove leading articles (The, A, An)
    - Remove subtitles (text after :, -, –, —)
    - Remove special characters
    - Normalize whitespace

    Examples:
        "The Stormlight Archive: The Way of Kings" → "stormlight archive"
        "Harry Potter and the Philosopher's Stone" → "harry potter and the philosophers stone"
        "Project Hail Mary" → "project hail mary"
    """
    if not title:
        return ""

    normalized = title.lower().strip()

    # Remove leading articles
    normalized = re.sub(r'^(the|a|an)\s+', '', normalized, flags=re.IGNORECASE)

    # Remove subtitles (after colon or dash variants)
    normalized = re.sub(r'[:\-–—].+$', '', normalized)

    # Remove special characters, keep only alphanumeric and spaces
    normalized = re.sub(r'[^\w\s]', '', normalized)

    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized


def normalize_author(author: str) -> str:
    """
    Normalize author name for matching.

    Rules:
    - Convert to lowercase
    - Normalize whitespace
    - Remove special characters except spaces

    Examples:
        "Brandon Sanderson" → "brandon sanderson"
        "J.R.R. Tolkien" → "jrr tolkien"
    """
    if not author:
        return ""

    normalized = author.lower().strip()

    # Remove periods and special characters
    normalized = re.sub(r'[^\w\s]', '', normalized)

    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized


def generate_card_guid(mam_id: str = "", title: str = "", author: str = "") -> str:
    """
    Generate unique identifier for a card.

    Priority:
    1. Use MAM ID if available (unique per torrent)
    2. Generate hash from normalized title + author

    Examples:
        mam_id="123456" → "mam-123456"
        title="Project Hail Mary", author="Andy Weir" → "card-abc123def"
    """
    if mam_id:
        return f"mam-{mam_id}"

    # Generate hash from normalized title + author
    normalized = f"{normalize_title(title)}||{normalize_author(author)}"
    return f"card-{simple_hash(normalized)}"


def simple_hash(text: str) -> str:
    """
    Generate simple hash for string (for cache keys, GUIDs, etc.).

    Uses basic string hashing algorithm, returns base36 representation.
    """
    hash_value = 0
    for char in text:
        hash_value = ((hash_value << 5) - hash_value) + ord(char)
        hash_value = hash_value & 0xFFFFFFFF  # Convert to 32-bit integer

    # Return absolute value as base36 string
    return format(abs(hash_value), 'x')[:12]  # Limit to 12 chars
