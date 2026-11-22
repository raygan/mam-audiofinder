"""Local file import: completed qB downloads -> Audiobookshelf library
(audiobooks) or Grimmory's ingest folder (ebooks).

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


# ---------------------------- Ebooks -> Grimmory ----------------------------
# Ebooks are always COPIED, never hardlinked or moved: ingest tools rewrite or
# delete what they process, which would corrupt or stop the seeding torrent.

DEFAULT_EBOOK_EXTENSIONS = ("epub", "pdf", "mobi", "azw3", "azw", "cbz", "cbr", "djvu", "fb2")
DEFAULT_FORMAT_PREFERENCE = ("epub", "azw3", "mobi", "pdf")
PARTIAL_SUFFIX = ".partial"


def parse_ext_list(raw, default) -> tuple[str, ...]:
    """"epub, .PDF ,mobi" -> ("epub", "pdf", "mobi")."""
    if isinstance(raw, (list, tuple)):
        items = raw
    else:
        items = str(raw or "").split(",")
    out = tuple(dict.fromkeys(e.strip().lower().lstrip(".") for e in items if str(e).strip()))
    return out or tuple(default)


def _ebook_files(src_root: Path, exts) -> list[Path]:
    if src_root.is_file():
        files = [src_root]
    else:
        files = sorted(p for p in src_root.rglob("*") if p.is_file())
    return [p for p in files if p.suffix.lower().lstrip(".") in exts and not p.name.startswith(".")]


def _rank(fmt: str, preference) -> tuple[int, str]:
    return (preference.index(fmt) if fmt in preference else len(preference), fmt)


def ebook_choices(src_root: Path, exts=DEFAULT_EBOOK_EXTENSIONS, preference=DEFAULT_FORMAT_PREFERENCE) -> list[dict]:
    """Ebook files in a torrent, grouped by book, for the user to choose from.

    A "book" is files in the same folder with the same name apart from the
    extension (book.epub + book.pdf). In each book the most preferred format
    is pre-selected; formats not in the preference list rank last. Paths are
    relative to the torrent's content root (for a single-file torrent, the
    file name).
    """
    base = src_root if src_root.is_dir() else src_root.parent
    groups: dict[tuple[str, str], list[Path]] = {}
    for f in _ebook_files(src_root, exts):
        rel = f.relative_to(base)
        groups.setdefault((str(rel.parent), f.stem.lower()), []).append(f)

    books = []
    for (_, _), files in groups.items():
        files.sort(key=lambda f: _rank(f.suffix.lower().lstrip("."), preference))
        books.append({
            "book": files[0].stem,
            "files": [{
                "path": str(f.relative_to(base)),
                "format": f.suffix.lower().lstrip("."),
                "size": f.stat().st_size,
                "selected": i == 0,
            } for i, f in enumerate(files)],
        })
    return books


def _resolve_choice(src_root: Path, rel: str, exts) -> Path:
    """A browser-supplied relative path -> a real ebook file inside the torrent."""
    base = (src_root if src_root.is_dir() else src_root.parent).resolve()
    if not rel or rel.startswith("/") or "\x00" in rel:
        raise ImportFailed(f"Invalid file choice: {rel!r}")
    p = (base / rel).resolve()
    try:
        p.relative_to(base)
    except ValueError:
        raise ImportFailed(f"File is outside the torrent: {rel!r}") from None
    if src_root.is_file() and p != src_root.resolve():
        raise ImportFailed(f"File is not part of this torrent: {rel!r}")
    if not p.is_file():
        raise ImportFailed(f"File not found in the torrent: {rel!r}", status=404)
    if p.suffix.lower().lstrip(".") not in exts:
        raise ImportFailed(f"Not an ebook file: {rel!r}")
    return p


def next_available_file(path: Path) -> Path:
    """book.epub -> book (2).epub -> book (3).epub ..."""
    if not path.exists():
        return path
    i = 2
    while True:
        cand = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not cand.exists():
            return cand
        i += 1


def copy_into_ingest(src: Path, ingest_dir: Path) -> Path:
    """Copy one file into the ingest folder without ever exposing a partial
    file under its real name: write a hidden .partial, then rename."""
    final = next_available_file(ingest_dir / src.name)
    partial = ingest_dir / f".{final.name}{PARTIAL_SUFFIX}"
    try:
        shutil.copyfile(src, partial)   # a new file: never a hardlink to the torrent
        shutil.copystat(src, partial)
        final = next_available_file(final)  # re-check right before the rename
        os.replace(partial, final)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return final


def ingest_dir_problem(path: str, write_test: bool = False) -> str | None:
    """None if the ingest folder is usable, else a message for the user.

    The cheap check (exists, is a folder, permission bits) runs on every
    /health; write_test=True also creates and removes a hidden file, which
    proves the container user (e.g. 99:100 on Unraid) can really write there.
    """
    if not path:
        return "EBOOK_INGEST_DIR is not set"
    p = Path(path)
    if not p.exists():
        return f"Ebook ingest folder does not exist inside the container: {path}"
    if not p.is_dir():
        return f"Ebook ingest path is not a folder: {path}"
    if not os.access(p, os.W_OK | os.X_OK):
        return f"Ebook ingest folder is not writable by this container's user (uid {os.getuid()}): {path}"
    if write_test:
        probe = p / f".mam-audiofinder-write-test-{os.getpid()}"
        try:
            probe.write_bytes(b"")
            probe.unlink()
        except OSError as e:
            probe.unlink(missing_ok=True)
            return f"Cannot write to the ebook ingest folder ({e.strerror}): {path}"
    return None


def import_ebooks(src_root: Path, chosen: list[str], ingest_dir: str, exts=DEFAULT_EBOOK_EXTENSIONS) -> list[Path]:
    """Copy the chosen ebook files (flat) into Grimmory's ingest folder."""
    if not chosen:
        raise ImportFailed("Choose at least one file to import")
    problem = ingest_dir_problem(ingest_dir)
    if problem:
        raise ImportFailed(problem, status=500)
    ingest = Path(ingest_dir)
    # Validate every choice before copying anything.
    files = list(dict.fromkeys(_resolve_choice(src_root, rel, exts) for rel in chosen))
    return [copy_into_ingest(f, ingest) for f in files]
