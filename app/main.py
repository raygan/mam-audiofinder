import os, json, re
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from datetime import datetime
from typing import List, Tuple

# ---------------------------- Config ----------------------------
CONFIG_PATH = os.getenv("APP_CONFIG_PATH", "/data/config.json")

def load_json_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

def is_setup_disabled() -> bool:
    val = os.getenv("DISABLE_SETUP", "")
    return str(val).strip().lower() in ("1", "true", "yes", "on")

def build_mam_cookie(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    # If user pasted full cookie header, use it as-is
    if "mam_id=" in raw or "mam_session=" in raw:
        return raw
    # If ASN single-token was pasted, wrap it
    if raw and "=" not in raw and ";" not in raw:
        return f"mam_id={raw}"
    return raw

def build_qb_path_map(raw_cfg, raw_env: str | None, dl_dir: str, qb_inner_prefix: str) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []

    # 1) JSON config: list of {qb_prefix, app_prefix}
    if isinstance(raw_cfg, list):
        for item in raw_cfg:
            if not isinstance(item, dict):
                continue
            qb = str(item.get("qb_prefix") or item.get("qb") or "").strip()
            app = str(item.get("app_prefix") or item.get("path") or "").strip()
            if not qb or not app:
                continue
            qb = qb.rstrip("/") or "/"
            app = app.rstrip("/") or "/"
            pairs.append((qb, app))

    # 2) Env string: "qb_prefix=app_prefix;other_qb=other_app"
    if not pairs and raw_env:
        val = raw_env.strip()
        if val:
            for part in val.split(";"):
                part = part.strip()
                if not part or "=" not in part:
                    continue
                qb, app = part.split("=", 1)
                qb = qb.strip().rstrip("/") or "/"
                app = app.strip().rstrip("/") or "/"
                if qb and app:
                    pairs.append((qb, app))

    # 3) Fallback: derive from QB_INNER_DL_PREFIX and DL_DIR
    if not pairs and qb_inner_prefix and dl_dir:
        qb = qb_inner_prefix.rstrip("/") or "/"
        app = dl_dir.rstrip("/") or "/"
        pairs.append((qb, app))

    return pairs

class Settings:
    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        cfg = load_json_config()

        self.MAM_BASE = cfg.get("MAM_BASE") or os.getenv("MAM_BASE", "https://www.myanonamouse.net")

        raw_cookie = cfg.get("MAM_COOKIE")
        if raw_cookie is None:
            raw_cookie = os.getenv("MAM_COOKIE", "")
        self.MAM_COOKIE = build_mam_cookie(raw_cookie)

        self.QB_URL = (cfg.get("QB_URL") or os.getenv("QB_URL", "http://qbittorrent:8080")).rstrip("/")
        self.QB_USER = cfg.get("QB_USER") or os.getenv("QB_USER", "admin")
        self.QB_PASS = cfg.get("QB_PASS") or os.getenv("QB_PASS", "adminadmin")
        self.QB_SAVEPATH = cfg.get("QB_SAVEPATH") or os.getenv("QB_SAVEPATH", "")
        self.QB_TAGS = cfg.get("QB_TAGS") or os.getenv("QB_TAGS", "MAM,audiobook")

        self.QB_CATEGORY = cfg.get("QB_CATEGORY") or os.getenv("QB_CATEGORY", "mam-audiofinder")
        self.QB_POSTIMPORT_CATEGORY = cfg.get("QB_POSTIMPORT_CATEGORY") or os.getenv("QB_POSTIMPORT_CATEGORY", "")

        self.DL_DIR = cfg.get("DL_DIR") or os.getenv("DL_DIR", "/media/torrents")
        self.LIB_DIR = cfg.get("LIB_DIR") or os.getenv("LIB_DIR", "/media/Books/Audiobooks")
        self.IMPORT_MODE = (cfg.get("IMPORT_MODE") or os.getenv("IMPORT_MODE", "link")).lower()

        self.QB_INNER_DL_PREFIX = cfg.get("QB_INNER_DL_PREFIX") or os.getenv("QB_INNER_DL_PREFIX", "/downloads")

        raw_pm_cfg = cfg.get("QB_PATH_MAP")
        raw_pm_env = os.getenv("QB_PATH_MAP")
        self.QB_PATH_MAP = build_qb_path_map(raw_pm_cfg, raw_pm_env, self.DL_DIR, self.QB_INNER_DL_PREFIX)

        self.UMASK = cfg.get("UMASK") or os.getenv("UMASK")

settings = Settings()

# apply UMASK for created files/dirs
_um = settings.UMASK
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

def needs_setup() -> bool:
    # Consider setup incomplete if we don't have a MAM cookie,
    # a library directory, or any qB path mapping.
    return not settings.MAM_COOKIE or not settings.LIB_DIR or not settings.QB_PATH_MAP

def setup_context(request: Request) -> dict:
    qb_prefix = settings.QB_INNER_DL_PREFIX
    app_prefix = settings.DL_DIR
    if settings.QB_PATH_MAP:
        qb_prefix, app_prefix = settings.QB_PATH_MAP[0]
    return {
        "request": request,
        "qb_url": settings.QB_URL,
        "qb_user": settings.QB_USER,
        "lib_dir": settings.LIB_DIR,
        "qb_prefix": qb_prefix,
        "app_prefix": app_prefix,
    }

class SetupPayload(BaseModel):
    mam_cookie: str | None = None
    qb_url: str | None = None
    qb_user: str | None = None
    qb_pass: str | None = None
    lib_dir: str | None = None
    qb_prefix: str | None = None
    app_prefix: str | None = None

# ---------------------------- App ----------------------------
app = FastAPI(title="MAM Audiobook Finder", version="0.3.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    setup_enabled = not is_setup_disabled()
    if needs_setup() and setup_enabled:
        return templates.TemplateResponse("setup.html", setup_context(request))
    return templates.TemplateResponse("index.html", {"request": request, "setup_enabled": setup_enabled})

@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    if is_setup_disabled():
        raise HTTPException(status_code=404, detail="Not found")
    return templates.TemplateResponse("setup.html", setup_context(request))

@app.post("/api/setup")
async def api_setup(body: SetupPayload):
    if is_setup_disabled():
        raise HTTPException(status_code=404, detail="Not found")
    cfg = load_json_config()
    if not isinstance(cfg, dict):
        cfg = {}

    if body.mam_cookie and body.mam_cookie.strip():
        cfg["MAM_COOKIE"] = body.mam_cookie.strip()
    if body.qb_url and body.qb_url.strip():
        cfg["QB_URL"] = body.qb_url.strip()
    if body.qb_user and body.qb_user.strip():
        cfg["QB_USER"] = body.qb_user.strip()
    if body.qb_pass:
        cfg["QB_PASS"] = body.qb_pass
    if body.lib_dir and body.lib_dir.strip():
        cfg["LIB_DIR"] = body.lib_dir.strip()

    if body.qb_prefix and body.qb_prefix.strip() and body.app_prefix and body.app_prefix.strip():
        qb_prefix = body.qb_prefix.strip().rstrip("/") or "/"
        app_prefix = body.app_prefix.strip().rstrip("/") or "/"
        cfg["QB_PATH_MAP"] = [{"qb_prefix": qb_prefix, "app_prefix": app_prefix}]

    # Persist config
    try:
        dirpath = os.path.dirname(CONFIG_PATH)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write config: {e}")

    settings.reload()
    return {"ok": True}

# ---------------------------- Search ----------------------------
@app.post("/search")
async def search(payload: dict):
    if not settings.MAM_COOKIE:
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
        "Cookie": settings.MAM_COOKIE,
        "Content-Type": "application/json",
        "Accept": "application/json, */*",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://www.myanonamouse.net",
        "Referer": "https://www.myanonamouse.net/",
    }
    params = {"dlLink": "1"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{settings.MAM_BASE}/tor/js/loadSearchJSONbasic.php",
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
    r = await client.post(f"{settings.QB_URL}/api/v2/auth/login",
                          data={"username": settings.QB_USER, "password": settings.QB_PASS},
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
    tag_list = [t.strip() for t in (settings.QB_TAGS or "").split(",") if t.strip()]
    if mam_id:
        tag_list.append(f"mamid={mam_id}")
    tag_str = ",".join(tag_list) if tag_list else ""

    direct_url = f"{settings.MAM_BASE}/tor/download.php/{dl}" if dl else None
    id_candidates = []
    if mam_id:
        id_candidates = [
            f"{settings.MAM_BASE}/tor/download.php?id={mam_id}",
            f"{settings.MAM_BASE}/tor/download.php?tid={mam_id}",
        ]

    qb_hash = None

    async with httpx.AsyncClient(timeout=60) as client:
        await qb_login(client)

        # Try URL add first if we have a cookie-less direct link
        if direct_url:
            form = {"urls": direct_url, "category": settings.QB_CATEGORY}
            if tag_str: form["tags"] = tag_str
            if settings.QB_SAVEPATH: form["savepath"] = settings.QB_SAVEPATH
            r = await client.post(f"{settings.QB_URL}/api/v2/torrents/add", data=form)
            if r.status_code == 200:
                # ask qB for hash (by tag)
                if mam_id:
                    info = await client.get(f"{settings.QB_URL}/api/v2/torrents/info",
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
            "Cookie": settings.MAM_COOKIE,
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
        data = {"category": settings.QB_CATEGORY}
        if tag_str: data["tags"] = tag_str
        if settings.QB_SAVEPATH: data["savepath"] = settings.QB_SAVEPATH

        r = await client.post(f"{settings.QB_URL}/api/v2/torrents/add", data=data, files=files)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"qB add (upload) failed: {r.status_code} {r.text[:160]}")

        # After upload, try to fetch hash
        if mam_id:
            info = await client.get(f"{settings.QB_URL}/api/v2/torrents/info",
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
        r = await c.get(f"{settings.QB_URL}/api/v2/torrents/info",
                        params={"category": settings.QB_CATEGORY, "filter": "completed"})
        r.raise_for_status()
        infos = r.json() if isinstance(r.json(), list) else []

        out = []
        for t in infos:
            h = t.get("hash")
            if not h:
                continue
            # files to determine single vs multi + root
            fr = await c.get(f"{settings.QB_URL}/api/v2/torrents/files", params={"hash": h})
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
    if settings.IMPORT_MODE == "move":
        shutil.move(src, dst)
    elif settings.IMPORT_MODE == "link":
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
        lr = c.post(f"{settings.QB_URL}/api/v2/auth/login",
                    data={"username": settings.QB_USER, "password": settings.QB_PASS})
        if lr.status_code != 200 or "Ok" not in lr.text:
            raise HTTPException(status_code=502, detail="qB login failed")

        # files (used to detect single-file)
        fr = c.get(f"{settings.QB_URL}/api/v2/torrents/files", params={"hash": h})
        if fr.status_code != 200:
            raise HTTPException(status_code=502, detail=f"qB files failed: {fr.status_code}")
        files = fr.json()
        if not files:
            raise HTTPException(status_code=404, detail="No files found for torrent")

        # properties (optional save_path)
        pr = c.get(f"{settings.QB_URL}/api/v2/torrents/properties", params={"hash": h})
        save_path = ""
        if pr.status_code == 200:
            save_path = (pr.json().get("save_path") or "").rstrip("/")

        # info (to get content_path)
        ir = c.get(f"{settings.QB_URL}/api/v2/torrents/info", params={"hashes": h})
        info_list = ir.json() if ir.status_code == 200 else []
        info = info_list[0] if isinstance(info_list, list) and info_list else {}
        content_path = info.get("content_path") or ""
        if not content_path:
            raise HTTPException(status_code=404, detail="Torrent content path not found")

    # map qB’s internal paths to this container’s paths
    def map_qb_path(p: str) -> str:
        p = (p or "").strip()
        if not p:
            return p
        for qb_prefix, app_prefix in settings.QB_PATH_MAP:
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

    src_root = Path(map_qb_path(content_path))

    # Destination: /library/Author/Title[/...]
    lib = Path(settings.LIB_DIR)
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
    if h and settings.QB_URL:
        try:
            with httpx.Client(timeout=15) as c2:
                lr = c2.post(
                    f"{settings.QB_URL}/api/v2/auth/login",
                    data={"username": settings.QB_USER, "password": settings.QB_PASS},
                )
                if lr.status_code == 200 and "Ok" in (lr.text or ""):
                    # Setting to empty string unsets the category on most qB versions.
                    # If your qB requires an existing category, set QB_POSTIMPORT_CATEGORY to that name.
                    c2.post(
                        f"{settings.QB_URL}/api/v2/torrents/setCategory",
                        data={"hashes": h, "category": settings.QB_POSTIMPORT_CATEGORY},
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
