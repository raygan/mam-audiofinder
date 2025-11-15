import os, json, re, asyncio, sys, hashlib
import httpx
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from datetime import datetime

# ---------------------------- Config ----------------------------
MAM_BASE = "https://www.myanonamouse.net"

def build_mam_cookie():
    raw = os.getenv("MAM_COOKIE", "").strip()
    # If user pasted full cookie header, use it as-is
    if "mam_id=" in raw or "mam_session=" in raw:
        return raw
    # If ASN single-token was pasted, wrap it
    if raw and "=" not in raw and ";" not in raw:
        return f"mam_id={raw}"
    return raw

MAM_COOKIE = build_mam_cookie()

QB_URL = os.getenv("QB_URL", "http://qbittorrent:8080").rstrip("/")
QB_USER = os.getenv("QB_USER", "admin")
QB_PASS = os.getenv("QB_PASS", "adminadmin")
QB_SAVEPATH = os.getenv("QB_SAVEPATH", "")  # optional
QB_TAGS     = os.getenv("QB_TAGS", "MAM,audiobook")  # optional

QB_CATEGORY = os.getenv("QB_CATEGORY", "mam-audiofinder")
QB_POSTIMPORT_CATEGORY = os.getenv("QB_POSTIMPORT_CATEGORY", "")  # "" = clear; or set e.g. "imported"

# Audiobookshelf integration (optional)
ABS_BASE_URL = os.getenv("ABS_BASE_URL", "").rstrip("/")
ABS_API_KEY = os.getenv("ABS_API_KEY", "")
ABS_LIBRARY_ID = os.getenv("ABS_LIBRARY_ID", "")
MAX_COVERS_SIZE_MB = int(os.getenv("MAX_COVERS_SIZE_MB", "500"))  # 0 = direct fetch only (not recommended)

# Covers directory for caching downloaded images
COVERS_DIR = Path("/data/covers")
COVERS_DIR.mkdir(parents=True, exist_ok=True)

DL_DIR = os.getenv("DL_DIR", "/media/torrents")
LIB_DIR = os.getenv("LIB_DIR", "/media/Books/Audiobooks")
IMPORT_MODE = os.getenv("IMPORT_MODE", "link")  # link|copy|move
FLATTEN_DISCS = os.getenv("FLATTEN_DISCS", "true").lower() in ("true", "1", "yes")  # flatten multi-disc to sequential files

QB_INNER_DL_PREFIX = os.getenv("QB_INNER_DL_PREFIX", "/downloads")  # qB container's mount point

# apply UMASK for created files/dirs
_um = os.getenv("UMASK")
if _um:
    try:
        os.umask(int(_um, 8))
    except Exception:
        pass

# ---------------------------- DB ----------------------------
# /data should be a volume/bind mount
engine = create_engine("sqlite:////data/history.db", future=True)
with engine.begin() as cx:
    cx.execute(text("""
        CREATE TABLE IF NOT EXISTS history (
          id INTEGER PRIMARY KEY,
          mam_id   TEXT,
          title    TEXT,
          dl       TEXT,
          added_at TEXT DEFAULT (datetime('now')),
          qb_status TEXT,
          qb_hash   TEXT
        )
    """))
    # Add columns if missing (idempotent)
    for ddl in (
        "ALTER TABLE history ADD COLUMN author   TEXT",
        "ALTER TABLE history ADD COLUMN narrator TEXT"
    ):
        try:
            cx.execute(text(ddl))
        except Exception:
            pass

    try:
        cx.execute(text("ALTER TABLE history ADD COLUMN imported_at TEXT"))
    except Exception:
        pass

    # Add Audiobookshelf columns if missing (idempotent)
    for ddl in (
        "ALTER TABLE history ADD COLUMN abs_item_id TEXT",
        "ALTER TABLE history ADD COLUMN abs_cover_url TEXT",
        "ALTER TABLE history ADD COLUMN abs_cover_cached_at TEXT"
    ):
        try:
            cx.execute(text(ddl))
        except Exception:
            pass

# Covers database - separate from history to cache covers before adding to qBittorrent
covers_engine = create_engine("sqlite:////data/covers.db", future=True)
with covers_engine.begin() as cx:
    cx.execute(text("""
        CREATE TABLE IF NOT EXISTS covers (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          mam_id TEXT UNIQUE NOT NULL,
          title TEXT,
          author TEXT,
          cover_url TEXT NOT NULL,
          abs_item_id TEXT,
          local_file TEXT,
          file_size INTEGER,
          fetched_at TEXT DEFAULT (datetime('now'))
        )
    """))
    # Add new columns if missing (idempotent)
    for ddl in (
        "ALTER TABLE covers ADD COLUMN local_file TEXT",
        "ALTER TABLE covers ADD COLUMN file_size INTEGER"
    ):
        try:
            cx.execute(text(ddl))
        except Exception:
            pass
    # Create index for faster lookups
    try:
        cx.execute(text("CREATE INDEX IF NOT EXISTS idx_covers_mam_id ON covers(mam_id)"))
        cx.execute(text("CREATE INDEX IF NOT EXISTS idx_covers_cover_url ON covers(cover_url)"))
    except Exception:
        pass

print("✓ Database schemas initialized", file=sys.stderr)

# ---------------------------- Startup Tests ----------------------------
async def test_abs_connection():
    """Test Audiobookshelf API connectivity on startup."""
    if not ABS_BASE_URL or not ABS_API_KEY:
        print("ℹ️  Audiobookshelf integration not configured (skipping connectivity test)", file=sys.stderr)
        return False

    try:
        print(f"🔍 Testing Audiobookshelf API connection to {ABS_BASE_URL}...", file=sys.stderr)
        headers = {"Authorization": f"Bearer {ABS_API_KEY}"}

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{ABS_BASE_URL}/api/me", headers=headers)

            if r.status_code == 200:
                data = r.json()
                username = data.get("username", "unknown")
                print(f"✅ Audiobookshelf API connected successfully (user: {username})", file=sys.stderr)
                return True
            else:
                print(f"❌ Audiobookshelf API test failed: HTTP {r.status_code}", file=sys.stderr)
                print(f"   Response: {r.text[:200]}", file=sys.stderr)
                return False

    except Exception as e:
        print(f"❌ Audiobookshelf API test failed with exception: {e}", file=sys.stderr)
        return False

# ---------------------------- App ----------------------------
app = FastAPI(title="MAM Audiobook Finder", version="0.3.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def startup_event():
    """Run startup tests."""
    await test_abs_connection()

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/config")
async def config():
    return {
        "import_mode": IMPORT_MODE,
        "flatten_discs": FLATTEN_DISCS,
    }

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ---------------------------- Cover Management ----------------------------
def get_covers_dir_size() -> int:
    """Get total size of covers directory in bytes."""
    total_size = 0
    try:
        for file in COVERS_DIR.iterdir():
            if file.is_file():
                total_size += file.stat().st_size
    except Exception as e:
        print(f"⚠️  Error calculating covers directory size: {e}", file=sys.stderr)
    return total_size

def cleanup_old_covers():
    """Remove oldest covers if directory exceeds MAX_COVERS_SIZE_MB."""
    if MAX_COVERS_SIZE_MB == 0:
        # No caching - should never get here, but just in case
        return

    max_bytes = MAX_COVERS_SIZE_MB * 1024 * 1024
    current_size = get_covers_dir_size()

    if current_size <= max_bytes:
        return

    print(f"📦 Covers cache ({current_size / 1024 / 1024:.1f}MB) exceeds limit ({MAX_COVERS_SIZE_MB}MB), cleaning up...", file=sys.stderr)

    # Get all cover files with their access times
    files_with_times = []
    try:
        for file in COVERS_DIR.iterdir():
            if file.is_file():
                files_with_times.append((file, file.stat().st_atime, file.stat().st_size))
    except Exception as e:
        print(f"❌ Error listing covers for cleanup: {e}", file=sys.stderr)
        return

    # Sort by access time (oldest first)
    files_with_times.sort(key=lambda x: x[1])

    # Remove oldest files until we're under the limit
    removed_count = 0
    removed_size = 0
    for file, _, size in files_with_times:
        if current_size - removed_size <= max_bytes:
            break
        try:
            file.unlink()
            removed_count += 1
            removed_size += size
            print(f"🗑️  Removed old cover: {file.name} ({size / 1024:.1f}KB)", file=sys.stderr)
        except Exception as e:
            print(f"⚠️  Failed to remove {file.name}: {e}", file=sys.stderr)

    if removed_count > 0:
        print(f"✅ Cleaned up {removed_count} covers, freed {removed_size / 1024 / 1024:.1f}MB", file=sys.stderr)

async def download_cover(url: str, mam_id: str) -> tuple[str | None, int]:
    """
    Download cover image and save to local storage.
    Returns tuple of (local_file_path, file_size) or (None, 0) on failure.
    """
    if MAX_COVERS_SIZE_MB == 0:
        # Direct fetch mode - don't cache
        print(f"ℹ️  MAX_COVERS_SIZE_MB=0, skipping download for direct fetch mode", file=sys.stderr)
        return None, 0

    try:
        print(f"⬇️  Downloading cover from: {url}", file=sys.stderr)

        async with httpx.AsyncClient(timeout=30) as client:
            # Add auth header if it's an ABS URL
            headers = {}
            if ABS_BASE_URL and url.startswith(ABS_BASE_URL):
                headers["Authorization"] = f"Bearer {ABS_API_KEY}"

            r = await client.get(url, headers=headers, follow_redirects=True)

            if r.status_code != 200:
                print(f"⚠️  Failed to download cover: HTTP {r.status_code}", file=sys.stderr)
                return None, 0

            # Determine file extension from Content-Type or URL
            content_type = r.headers.get("Content-Type", "")
            ext = ".jpg"  # default
            if "png" in content_type:
                ext = ".png"
            elif "webp" in content_type:
                ext = ".webp"
            elif "gif" in content_type:
                ext = ".gif"
            elif url.endswith(".png"):
                ext = ".png"
            elif url.endswith(".webp"):
                ext = ".webp"

            # Save to file
            filename = f"{mam_id}{ext}"
            filepath = COVERS_DIR / filename
            file_size = len(r.content)

            filepath.write_bytes(r.content)
            print(f"✅ Saved cover: {filename} ({file_size / 1024:.1f}KB)", file=sys.stderr)

            # Check if we need to cleanup old covers
            cleanup_old_covers()

            return str(filepath), file_size

    except Exception as e:
        print(f"❌ Failed to download cover from {url}: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return None, 0

@app.get("/covers/{filename}")
async def serve_cover(filename: str):
    """Serve cached cover images."""
    # Sanitize filename
    filename = Path(filename).name  # Remove any path traversal attempts
    filepath = COVERS_DIR / filename

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Cover not found")

    return FileResponse(filepath)

# ---------------------------- Audiobookshelf helpers ----------------------------
def get_cached_cover(mam_id: str) -> dict:
    """
    Get cached cover from covers database by MAM ID.
    Returns dict with 'cover_url' (local or remote), 'item_id', 'is_local' if found, else empty dict.
    """
    if not mam_id:
        print(f"⚠️  get_cached_cover called with empty mam_id", file=sys.stderr)
        return {}

    try:
        with covers_engine.begin() as cx:
            row = cx.execute(text("""
                SELECT cover_url, abs_item_id, fetched_at, title, author, local_file
                FROM covers
                WHERE mam_id = :mam_id
                LIMIT 1
            """), {"mam_id": mam_id}).fetchone()

            if row and row[0]:
                local_file = row[5]
                # Check if local file exists
                if local_file and Path(local_file).exists():
                    # Return local cover path
                    filename = Path(local_file).name
                    local_url = f"/covers/{filename}"
                    print(f"📦 Cache HIT (local) for MAM ID {mam_id}: {local_url} (title: '{row[3]}', fetched: {row[2]})", file=sys.stderr)
                    return {"cover_url": local_url, "item_id": row[1], "is_local": True}
                elif MAX_COVERS_SIZE_MB == 0:
                    # Direct fetch mode - return remote URL
                    print(f"📦 Cache HIT (direct) for MAM ID {mam_id}: {row[0]} (title: '{row[3]}', fetched: {row[2]})", file=sys.stderr)
                    return {"cover_url": row[0], "item_id": row[1], "is_local": False}
                else:
                    # Local file missing but should exist - return remote URL as fallback
                    print(f"⚠️  Cache HIT but local file missing for MAM ID {mam_id}, using remote URL", file=sys.stderr)
                    return {"cover_url": row[0], "item_id": row[1], "is_local": False}

        print(f"📦 Cache MISS for MAM ID {mam_id}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"❌ CRITICAL: Failed to get cached cover for MAM ID {mam_id}: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return {}

async def save_cover_to_cache(mam_id: str, cover_url: str, title: str = "", author: str = "", item_id: str = None):
    """
    Save cover URL to covers database and download the image to local storage.
    Uses INSERT OR REPLACE to handle duplicates.
    Also checks if the cover_url is already used by another MAM ID to avoid duplicate downloads.
    """
    if not mam_id:
        print(f"⚠️  save_cover_to_cache called with empty mam_id", file=sys.stderr)
        return

    if not cover_url:
        print(f"⚠️  save_cover_to_cache called with empty cover_url for MAM ID {mam_id}", file=sys.stderr)
        return

    try:
        print(f"💾 Attempting to cache cover for MAM ID {mam_id}: {cover_url}", file=sys.stderr)

        local_file = None
        file_size = 0

        # Check if we should download the cover
        with covers_engine.begin() as cx:
            # Check if this cover URL is already cached for a different MAM ID
            existing = cx.execute(text("""
                SELECT mam_id, title, local_file, file_size FROM covers
                WHERE cover_url = :cover_url AND mam_id != :mam_id LIMIT 1
            """), {"cover_url": cover_url, "mam_id": mam_id}).fetchone()

            if existing and existing[2]:
                # Reuse existing downloaded cover
                local_file = existing[2]
                file_size = existing[3] or 0
                print(f"ℹ️  Cover URL already cached for MAM ID {existing[0]} ('{existing[1]}'). Reusing local file: {Path(local_file).name}", file=sys.stderr)
            elif MAX_COVERS_SIZE_MB > 0:
                # Download the cover
                local_file, file_size = await download_cover(cover_url, mam_id)

        # Get the final cover URL (local or remote)
        final_cover_url = cover_url
        if local_file and Path(local_file).exists():
            filename = Path(local_file).name
            final_cover_url = f"/covers/{filename}"

        # Insert or replace the cover entry
        with covers_engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO covers (mam_id, title, author, cover_url, abs_item_id, local_file, file_size, fetched_at)
                VALUES (:mam_id, :title, :author, :cover_url, :item_id, :local_file, :file_size, :fetched_at)
                ON CONFLICT(mam_id) DO UPDATE SET
                    cover_url = :cover_url,
                    abs_item_id = :item_id,
                    title = :title,
                    author = :author,
                    local_file = :local_file,
                    file_size = :file_size,
                    fetched_at = :fetched_at
            """), {
                "mam_id": mam_id,
                "title": title,
                "author": author,
                "cover_url": cover_url,  # Keep original remote URL
                "item_id": item_id,
                "local_file": local_file,
                "file_size": file_size,
                "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            })

            print(f"✅ Cached cover for MAM ID {mam_id}: {final_cover_url}", file=sys.stderr)

        # Also update history table if there's an entry
        try:
            with engine.begin() as cx:
                result = cx.execute(text("""
                    UPDATE history
                    SET abs_cover_url = :cover_url,
                        abs_item_id = :item_id,
                        abs_cover_cached_at = :cached_at
                    WHERE mam_id = :mam_id
                """), {
                    "mam_id": mam_id,
                    "cover_url": final_cover_url,  # Use local URL if available
                    "item_id": item_id,
                    "cached_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                })
                if result.rowcount > 0:
                    print(f"✅ Updated {result.rowcount} history row(s) with cover for MAM ID {mam_id}", file=sys.stderr)
        except Exception as he:
            print(f"⚠️  Failed to update history table (non-critical): {he}", file=sys.stderr)

    except Exception as e:
        print(f"❌ CRITICAL: Failed to cache cover for MAM ID {mam_id}: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

async def fetch_abs_cover(title: str, author: str = "", mam_id: str = "") -> dict:
    """
    Fetch cover image URL from Audiobookshelf.
    Returns dict with 'cover_url' and 'item_id' if found, else empty dict.
    Checks cache first if mam_id is provided.
    """
    print(f"🔍 Fetching cover for: '{title}' by '{author}' (MAM ID: {mam_id or 'N/A'})", file=sys.stderr)

    # Check cache first
    if mam_id:
        cached = get_cached_cover(mam_id)
        if cached:
            return cached

    if not ABS_BASE_URL or not ABS_API_KEY:
        print(f"⚠️  ABS not configured, skipping cover fetch for '{title}'", file=sys.stderr)
        return {}

    if not title:
        print(f"⚠️  No title provided, skipping cover fetch", file=sys.stderr)
        return {}

    try:
        headers = {"Authorization": f"Bearer {ABS_API_KEY}"}
        params = {"title": title}
        if author:
            params["author"] = author

        print(f"🌐 Calling ABS /api/search/covers with params: {params}", file=sys.stderr)

        async with httpx.AsyncClient(timeout=10) as client:
            # Try the search/covers endpoint first
            r = await client.get(
                f"{ABS_BASE_URL}/api/search/covers",
                headers=headers,
                params=params
            )

            print(f"📡 ABS /api/search/covers response: HTTP {r.status_code}", file=sys.stderr)

            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])
                print(f"📊 Got {len(results)} results from /api/search/covers", file=sys.stderr)

                if results and len(results) > 0:
                    # Take the first result
                    first_result = results[0]
                    cover_url = None
                    if isinstance(first_result, str):
                        # It's just a URL
                        cover_url = first_result
                        print(f"✅ Found cover URL (string): {cover_url}", file=sys.stderr)
                    elif isinstance(first_result, dict):
                        # It might have more structure
                        cover_url = first_result.get("cover") or first_result.get("url") or str(first_result)
                        print(f"✅ Found cover URL (dict): {cover_url}", file=sys.stderr)

                    if cover_url:
                        # Cache the result if we have a MAM ID
                        if mam_id:
                            await save_cover_to_cache(mam_id, cover_url, title, author, None)
                            # Get the potentially updated cover URL (local path)
                            cached = get_cached_cover(mam_id)
                            if cached:
                                return cached
                        return {"cover_url": cover_url, "item_id": None}
                else:
                    print(f"⚠️  No results from /api/search/covers", file=sys.stderr)
            else:
                print(f"⚠️  /api/search/covers failed: {r.text[:200]}", file=sys.stderr)

        # If no results from search/covers, try searching library items
        if ABS_LIBRARY_ID:
            print(f"🔍 Trying library search with ID: {ABS_LIBRARY_ID}", file=sys.stderr)
            async with httpx.AsyncClient(timeout=10) as client:
                # Search within library using filter
                r = await client.get(
                    f"{ABS_BASE_URL}/api/libraries/{ABS_LIBRARY_ID}/items",
                    headers=headers,
                    params={"limit": 5, "minified": "1"}
                )

                print(f"📡 ABS library items response: HTTP {r.status_code}", file=sys.stderr)

                if r.status_code == 200:
                    data = r.json()
                    results = data.get("results", [])
                    print(f"📊 Got {len(results)} items from library", file=sys.stderr)

                    # Simple title matching (case-insensitive)
                    title_lower = title.lower()
                    for item in results:
                        item_title = (item.get("media", {}).get("metadata", {}).get("title") or "").lower()
                        if title_lower in item_title or item_title in title_lower:
                            item_id = item.get("id")
                            if item_id:
                                # Build cover URL
                                cover_url = f"{ABS_BASE_URL}/api/items/{item_id}/cover"
                                print(f"✅ Found cover in library: {cover_url}", file=sys.stderr)
                                # Cache the result if we have a MAM ID
                                if mam_id:
                                    await save_cover_to_cache(mam_id, cover_url, title, author, item_id)
                                    # Get the potentially updated cover URL (local path)
                                    cached = get_cached_cover(mam_id)
                                    if cached:
                                        return cached
                                return {"cover_url": cover_url, "item_id": item_id}
                    print(f"⚠️  No matching items in library for '{title}'", file=sys.stderr)
                else:
                    print(f"⚠️  Library search failed: {r.text[:200]}", file=sys.stderr)
        else:
            print(f"ℹ️  No ABS_LIBRARY_ID configured, skipping library search", file=sys.stderr)

        print(f"❌ No cover found for '{title}'", file=sys.stderr)
        return {}

    except Exception as e:
        # Don't fail the whole request if ABS is down
        print(f"❌ Audiobookshelf cover fetch failed for '{title}': {type(e).__name__}: {e}", file=sys.stderr)
        return {}

# ---------------------------- Search ----------------------------
@app.post("/search")
async def search(payload: dict):
    if not MAM_COOKIE:
        raise HTTPException(status_code=500, detail="MAM_COOKIE not set on server")

    tor = payload.get("tor", {}) or {}
    tor.setdefault("text", "")
    tor.setdefault("srchIn", ["title", "author", "narrator"])
    tor.setdefault("searchType", "all")
    tor.setdefault("sortType", "default")
    tor.setdefault("startNumber", "0")
    tor.setdefault("main_cat", ["13"])  # Audiobooks

    perpage = payload.get("perpage", 25)
    body = {"tor": tor, "perpage": perpage}

    headers = {
        "Cookie": MAM_COOKIE,
        "Content-Type": "application/json",
        "Accept": "application/json, */*",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://www.myanonamouse.net",
        "Referer": "https://www.myanonamouse.net/",
    }
    params = {"dlLink": "1"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{MAM_BASE}/tor/js/loadSearchJSONbasic.php",
                                  headers=headers, params=params, json=body)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"MAM request failed: {e}")

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"MAM HTTP {r.status_code}: {r.text[:300]}")
    try:
        raw = r.json()
    except ValueError:
        raise HTTPException(status_code=502, detail=f"MAM returned non-JSON. Body: {r.text[:300]}")

    def flatten(v):
        # {"8320":"John Steinbeck"} or JSON-string -> "John Steinbeck"
        if isinstance(v, dict):
            return ", ".join(str(x) for x in v.values())
        if isinstance(v, list):
            return ", ".join(str(x) for x in v)
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("{") or s.startswith("["):
                try:
                    obj = json.loads(s)
                    if isinstance(obj, dict):
                        return ", ".join(str(x) for x in obj.values())
                    if isinstance(obj, list):
                        return ", ".join(str(x) for x in obj)
                except Exception:
                    pass
            s = re.sub(r'^\{|\}$', '', s)
            parts = []
            for chunk in s.split(","):
                parts.append(chunk.split(":", 1)[-1])
            parts = [p.strip().strip('"').strip("'") for p in parts if p.strip()]
            return ", ".join(parts)
        return "" if v is None else str(v)

    def detect_format(item: dict) -> str:
        for key in ("format", "filetype", "container", "encoding", "format_name"):
            val = item.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        name = (item.get("title") or item.get("name") or "")
        toks = re.findall(r'(?i)\b(mp3|m4b|flac|aac|ogg|opus|wav|alac|ape|epub|pdf|mobi|azw3|cbz|cbr)\b', name)
        if toks:
            uniq = list(dict.fromkeys(t.upper() for t in toks))
            return "/".join(uniq)
        return ""

    out = []
    for item in raw.get("data", []):
        out.append({
            "id": str(item.get("id") or item.get("tid") or ""),
            "title": item.get("title") or item.get("name"),
            "author_info": flatten(item.get("author_info")),
            "narrator_info": flatten(item.get("narrator_info")),
            "format": detect_format(item),
            "size": item.get("size"),
            "seeders": item.get("seeders"),
            "leechers": item.get("leechers"),
            "catname": item.get("catname"),
            "added": item.get("added"),
            "dl": item.get("dl"),
        })

    # Fetch covers from Audiobookshelf (if configured)
    if ABS_BASE_URL and ABS_API_KEY and out:
        print(f"📚 Fetching covers for {len(out)} search results...", file=sys.stderr)
        # Fetch covers in parallel for all results
        cover_tasks = []
        for result in out:
            title = result.get("title") or ""
            author = result.get("author_info") or ""
            mam_id = result.get("id") or ""
            cover_tasks.append(fetch_abs_cover(title, author, mam_id))

        cover_results = await asyncio.gather(*cover_tasks, return_exceptions=True)

        # Add cover URLs to results
        covers_added = 0
        for i, cover_data in enumerate(cover_results):
            if isinstance(cover_data, dict) and cover_data:
                out[i]["abs_cover_url"] = cover_data.get("cover_url")
                out[i]["abs_item_id"] = cover_data.get("item_id")
                if cover_data.get("cover_url"):
                    covers_added += 1
            elif isinstance(cover_data, Exception):
                print(f"❌ Cover fetch exception for result {i}: {cover_data}", file=sys.stderr)

        print(f"✅ Added {covers_added} cover URLs to search results", file=sys.stderr)
    else:
        if not ABS_BASE_URL or not ABS_API_KEY:
            print(f"ℹ️  Skipping cover fetch: ABS not configured (URL={bool(ABS_BASE_URL)}, KEY={bool(ABS_API_KEY)})", file=sys.stderr)
        elif not out:
            print(f"ℹ️  Skipping cover fetch: no search results", file=sys.stderr)

    return JSONResponse({
        "results": out,
        "total": raw.get("total"),
        "total_found": raw.get("total_found"),
    })

# ---------------------------- qB API helpers ----------------------------
async def qb_login(client: httpx.AsyncClient):
    r = await client.post(f"{QB_URL}/api/v2/auth/login",
                          data={"username": QB_USER, "password": QB_PASS},
                          timeout=20)
    if r.status_code != 200 or "Ok" not in (r.text or ""):
        raise HTTPException(status_code=502, detail=f"qB login failed: {r.status_code} {r.text[:120]}")

# ---------------------------- Add-to-qB ----------------------------
class AddBody(BaseModel):
    id: str | int | None = None
    title: str | None = None
    dl: str | None = None
    author: str | None = None
    narrator: str | None = None
    abs_cover_url: str | None = None
    abs_item_id: str | None = None

@app.post("/add")
async def add_to_qb(body: AddBody):
    mam_id = ("" if body.id is None else str(body.id)).strip()
    title = (body.title or "").strip()
    author = (body.author or "").strip()
    narrator = (body.narrator or "").strip()
    dl = (body.dl or "").strip()

    if not mam_id and not dl:
        raise HTTPException(status_code=400, detail="Missing MAM id and dl; need at least one")

    # tags: existing + mamid=<id>
    tag_list = [t.strip() for t in (QB_TAGS or "").split(",") if t.strip()]
    if mam_id:
        tag_list.append(f"mamid={mam_id}")
    tag_str = ",".join(tag_list) if tag_list else ""

    direct_url = f"{MAM_BASE}/tor/download.php/{dl}" if dl else None
    id_candidates = []
    if mam_id:
        id_candidates = [
            f"{MAM_BASE}/tor/download.php?id={mam_id}",
            f"{MAM_BASE}/tor/download.php?tid={mam_id}",
        ]

    qb_hash = None

    async with httpx.AsyncClient(timeout=60) as client:
        await qb_login(client)

        # Try URL add first if we have a cookie-less direct link
        if direct_url:
            form = {"urls": direct_url, "category": QB_CATEGORY}
            if tag_str: form["tags"] = tag_str
            if QB_SAVEPATH: form["savepath"] = QB_SAVEPATH
            r = await client.post(f"{QB_URL}/api/v2/torrents/add", data=form)
            if r.status_code == 200:
                # ask qB for hash (by tag)
                if mam_id:
                    info = await client.get(f"{QB_URL}/api/v2/torrents/info",
                                            params={"tag": f"mamid={mam_id}", "filter": "all"})
                    try:
                        arr = info.json()
                        if isinstance(arr, list) and arr:
                            tlow = title.lower()
                            pick = None
                            for tor in arr:
                                nm = (tor.get("name") or "").lower()
                                if tlow and nm.startswith(tlow[:20]):
                                    pick = tor; break
                            qb_hash = (pick or arr[0]).get("hash")
                    except Exception:
                        pass

                with engine.begin() as cx:
                    cx.execute(text("""
                        INSERT INTO history (mam_id, title, author, narrator, dl, qb_status, qb_hash, added_at,
                                           abs_cover_url, abs_item_id, abs_cover_cached_at)
                        VALUES (:mam_id, :title, :author, :narrator, :dl, :qb_status, :qb_hash, :added_at,
                                :abs_cover_url, :abs_item_id, :abs_cover_cached_at)
                    """), {
                        "mam_id": mam_id, "title": title, "author": author, "narrator": narrator,
                        "dl": dl, "qb_status": "added", "qb_hash": qb_hash,
                        "added_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        "abs_cover_url": body.abs_cover_url,
                        "abs_item_id": body.abs_item_id,
                        "abs_cover_cached_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") if body.abs_cover_url else None,
                    })
                return {"ok": True}
            # else: fall through to cookie fetch

        # Cookie-authenticated fetch of .torrent, then upload
        mam_headers = {
            "Cookie": MAM_COOKIE,
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/x-bittorrent, */*",
            "Referer": "https://www.myanonamouse.net/",
            "Origin": "https://www.myanonamouse.net",
        }
        torrent_bytes = None
        for url in id_candidates:
            resp = await client.get(url, headers=mam_headers)
            if resp.status_code == 200 and resp.content:
                torrent_bytes = resp.content
                break

        if not torrent_bytes:
            raise HTTPException(status_code=502, detail="Could not fetch .torrent from MAM (no dl hash and cookie fetch failed).")

        files = {"torrents": ("mam.torrent", torrent_bytes, "application/x-bittorrent")}
        data = {"category": QB_CATEGORY}
        if tag_str: data["tags"] = tag_str
        if QB_SAVEPATH: data["savepath"] = QB_SAVEPATH

        r = await client.post(f"{QB_URL}/api/v2/torrents/add", data=data, files=files)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"qB add (upload) failed: {r.status_code} {r.text[:160]}")

        # After upload, try to fetch hash
        if mam_id:
            info = await client.get(f"{QB_URL}/api/v2/torrents/info",
                                    params={"tag": f"mamid={mam_id}", "filter": "all"})
            try:
                arr = info.json()
                if isinstance(arr, list) and arr:
                    qb_hash = arr[0].get("hash")
            except Exception:
                pass

        with engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO history (mam_id, title, author, narrator, dl, qb_status, qb_hash, added_at,
                                   abs_cover_url, abs_item_id, abs_cover_cached_at)
                VALUES (:mam_id, :title, :author, :narrator, :dl, :qb_status, :qb_hash, :added_at,
                        :abs_cover_url, :abs_item_id, :abs_cover_cached_at)
            """), {
                "mam_id": mam_id, "title": title, "author": author, "narrator": narrator,
                "dl": dl, "qb_status": "added", "qb_hash": qb_hash,
                "added_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "abs_cover_url": body.abs_cover_url,
                "abs_item_id": body.abs_item_id,
                "abs_cover_cached_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") if body.abs_cover_url else None,
            })

    return {"ok": True}

# ---------------------------- History ----------------------------
@app.get("/history")
def history():
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT id, mam_id, title, author, narrator, dl, qb_hash, added_at, qb_status,
                   abs_cover_url, abs_item_id
            FROM history
            ORDER BY id DESC
            LIMIT 200
        """)).mappings().all()
    return {"items": list(rows)}

@app.delete("/history/{row_id}")
def delete_history(row_id: int):
    with engine.begin() as cx:
        cx.execute(text("DELETE FROM history WHERE id = :id"), {"id": row_id})
    return {"ok": True}
    
# ---------------------------- List Importable ----------------------------
@app.get("/qb/torrents")
async def qb_torrents():
    async with httpx.AsyncClient(timeout=30) as c:
        await qb_login(c)
        # completed in our category
        r = await c.get(f"{QB_URL}/api/v2/torrents/info",
                        params={"category": QB_CATEGORY, "filter": "completed"})
        r.raise_for_status()
        infos = r.json() if isinstance(r.json(), list) else []

        out = []
        for t in infos:
            h = t.get("hash")
            if not h:
                continue
            # files to determine single vs multi + root
            fr = await c.get(f"{QB_URL}/api/v2/torrents/files", params={"hash": h})
            files = fr.json() if fr.status_code == 200 else []
            # compute top-level root (before first '/')
            roots = set()
            for f in files:
                name = (f.get("name") or "").lstrip("/")
                roots.add(name.split("/", 1)[0])
            root = (list(roots)[0] if roots else t.get("name") or "")
            single_file = len(files) == 1 and "/" not in (files[0].get("name") or "")
            out.append({
                "hash": h,
                "name": t.get("name"),
                "save_path": t.get("save_path"),  # absolute host path, but we mounted /media so it should start with /media
                "root": root,
                "single_file": single_file,
                "size": t.get("total_size"),
                "added_on": t.get("added_on"),
            })
        return {"items": out}
        
# ---------------------------- Perform Import ----------------------------

from pathlib import Path
import shutil

AUDIO_EXTS = None  # copy everything except .cue (per your request)

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

def try_hardlink(src: Path, dst: Path):
    try:
        os.link(src, dst)
        return True
    except Exception:
        return False

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
    author: str
    title: str
    hash: str
    history_id: int | None = None

@app.post("/import")
def do_import(body: ImportBody):
    author = sanitize(body.author)
    title = sanitize(body.title)
    h = body.hash

    # Query qB for files, properties, and content_path
    with httpx.Client(timeout=30) as c:
        # login
        lr = c.post(f"{QB_URL}/api/v2/auth/login",
                    data={"username": QB_USER, "password": QB_PASS})
        if lr.status_code != 200 or "Ok" not in lr.text:
            raise HTTPException(status_code=502, detail="qB login failed")

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

    # map qB’s internal paths to this container’s paths
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
                lr = c2.post(
                    f"{QB_URL}/api/v2/auth/login",
                    data={"username": QB_USER, "password": QB_PASS},
                )
                if lr.status_code == 200 and "Ok" in (lr.text or ""):
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