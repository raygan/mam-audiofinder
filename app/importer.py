"""Local file import: completed qB downloads -> Audiobookshelf library.

No network here; qB lookups happen in qb.py, MAM never.
"""
import os, re, shutil
from pathlib import Path
from typing import Iterable, Tuple


class ImportFailed(Exception):
    def __init__(self, detail: str, status: int = 400):
        self.detail = detail
        self.status = status
        super().__init__(detail)


def sanitize(name: str) -> str:
    s = name.strip().replace(":", " -").replace("\\", "﹨").replace("/", "﹨")
    return re.sub(r"\s+", " ", s)[:200] or "Unknown"


def next_available(path: Path) -> Path:
    if not path.exists():
        return path
    i = 2
    while True:
        cand = path.with_name(f"{path.name} ({i})")
        if not cand.exists():
            return cand
        i += 1


def try_hardlink(src: Path, dst: Path) -> bool:
    try:
        os.link(src, dst)
        return True
    except Exception:
        return False


def copy_one(src: Path, dst: Path, mode: str):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if mode == "move":
        shutil.move(src, dst)
    elif mode == "link":
        if not try_hardlink(src, dst):
            shutil.copy2(src, dst)
    else:  # copy
        shutil.copy2(src, dst)


def map_qb_path(p: str, path_map: Iterable[Tuple[str, str]]) -> str:
    """Map qB's internal path to this container's path."""
    p = (p or "").strip()
    if not p:
        return p
    for qb_prefix, app_prefix in path_map:
        qb = qb_prefix.rstrip("/") or "/"
        if p == qb or p.startswith(qb + "/"):
            return (app_prefix.rstrip("/") or "/") + p[len(qb):]
    if p.startswith("/media/"):
        return p
    # Back-compat for common Unraid-style host paths mounted at /media
    if p.startswith("/mnt/user/media"):
        return p.replace("/mnt/user/media", "/media", 1)
    if p.startswith("/mnt/media"):
        return p.replace("/mnt/media", "/media", 1)
    return p


def import_audiobook(src_root: Path, author: str, title: str, lib_dir: str, mode: str) -> Path:
    """Copy/link/move everything except .cue into <lib>/<Author>/<Title>[ (n)]."""
    author_dir = Path(lib_dir) / sanitize(author)
    author_dir.mkdir(parents=True, exist_ok=True)
    dest_dir = next_available(author_dir / sanitize(title))

    if src_root.is_file():
        if src_root.suffix.lower() == ".cue":
            raise ImportFailed("Only .cue file found; nothing to import")
        copy_one(src_root, dest_dir / src_root.name, mode)
    else:
        for p in src_root.rglob("*"):
            if not p.is_file() or p.suffix.lower() == ".cue":
                continue
            copy_one(p, dest_dir / p.relative_to(src_root), mode)
    return dest_dir
