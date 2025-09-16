import os, json, re
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
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

DL_DIR = os.getenv("DL_DIR", "/media/torrents")
LIB_DIR = os.getenv("LIB_DIR", "/media/Books/Audiobooks")
IMPORT_MODE = os.getenv("IMPORT_MODE", "link")  # link|copy|move

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

# ---------------------------- App ----------------------------
app = FastAPI(title="MAM Audiobook Finder", version="0.3.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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
                        INSERT INTO history (mam_id, title, author, narrator, dl, qb_status, qb_hash, added_at)
                        VALUES (:mam_id, :title, :author, :narrator, :dl, :qb_status, :qb_hash, :added_at)
                    """), {
                        "mam_id": mam_id, "title": title, "author": author, "narrator": narrator,
                        "dl": dl, "qb_status": "added", "qb_hash": qb_hash,
                        "added_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
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
                INSERT INTO history (mam_id, title, author, narrator, dl, qb_status, qb_hash, added_at)
                VALUES (:mam_id, :title, :author, :narrator, :dl, :qb_status, :qb_hash, :added_at)
            """), {
                "mam_id": mam_id, "title": title, "author": author, "narrator": narrator,
                "dl": dl, "qb_status": "added", "qb_hash": qb_hash,
                "added_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            })

    return {"ok": True}

# ---------------------------- History ----------------------------
@app.get("/history")
def history():
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT id, mam_id, title, author, narrator, dl, qb_hash, added_at, qb_status
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

def try_hardlink(src: Path, dst: Path):
    try:
        os.link(src, dst)
        return True
    except Exception:
        return False

def copy_one(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if IMPORT_MODE == "move":
        shutil.move(src, dst)
    elif IMPORT_MODE == "link":
        if not try_hardlink(src, dst):
            shutil.copy2(src, dst)
    else:  # copy
        shutil.copy2(src, dst)

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

    # Destination: /library/Author/Title[/...]
    lib = Path(LIB_DIR)
    author_dir = lib / author
    author_dir.mkdir(parents=True, exist_ok=True)
    dest_dir = next_available(author_dir / title)

    # Copy/link all (skip .cue)
    if src_root.is_file():
        if src_root.suffix.lower() == ".cue":
            raise HTTPException(status_code=400, detail="Only .cue file found; nothing to import")
        copy_one(src_root, dest_dir / src_root.name)
    else:
        for p in src_root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() == ".cue":
                continue
            rel = p.relative_to(src_root)
            copy_one(p, dest_dir / rel)

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

    return {"ok": True, "dest": str(dest_dir)}