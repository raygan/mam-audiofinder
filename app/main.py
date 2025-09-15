import os, json, re
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# NEW: DB + time
from sqlalchemy import create_engine, text
from datetime import datetime

MAM_COOKIE = os.getenv("MAM_COOKIE", "").strip()
MAM_BASE = "https://www.myanonamouse.net"

# qB settings
QB_URL = os.getenv("QB_URL", "http://qbittorrent:8080").rstrip("/")
QB_USER = os.getenv("QB_USER", "admin")
QB_PASS = os.getenv("QB_PASS", "adminadmin")
QB_SAVEPATH = os.getenv("QB_SAVEPATH", "")  # optional
QB_TAGS = os.getenv("QB_TAGS", "")  # optional

# DB (volume-mounted at /data)
engine = create_engine("sqlite:////data/history.db", future=True)
with engine.begin() as cx:
    cx.execute(text("""
    CREATE TABLE IF NOT EXISTS history (
      id INTEGER PRIMARY KEY,
      mam_id TEXT,
      title TEXT,
      dl TEXT,
      added_at TEXT DEFAULT (datetime('now')),
      qb_status TEXT,
      qb_hash TEXT
    )
    """))

app = FastAPI(title="MAM Audiobook Finder", version="0.2.0")

# Static & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/search")
async def search(payload: dict):
    if not MAM_COOKIE:
        raise HTTPException(status_code=500, detail="MAM_COOKIE not set on server")

    # Defaults; allow client to override
    tor = payload.get("tor", {})
    tor.setdefault("text", "")
    tor.setdefault("srchIn", ["title", "author", "narrator"])  # per docs
    tor.setdefault("searchType", "all")
    tor.setdefault("sortType", "default")
    tor.setdefault("startNumber", "0")
    # Audiobooks by default
    tor.setdefault("main_cat", ["13"])  # 13 = AudioBooks

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
    # dlLink flag returns the per-user hash for cookie-less download
    params = {"dlLink": "1"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{MAM_BASE}/tor/js/loadSearchJSONbasic.php",
                                  headers=headers, params=params, json=body)
            r.raise_for_status()
            raw = r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"MAM request failed: {e}")

    # Normalize a subset for UI
    def flatten(v):
        # {"8320": "John Steinbeck"} -> "John Steinbeck"
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
            s = re.sub(r'^\{|\}$', '', s)  # trim outer {}
            parts = []
            for chunk in s.split(","):
                if ":" in chunk:
                    parts.append(chunk.split(":", 1)[1])
                else:
                    parts.append(chunk)
            parts = [p.strip().strip('"').strip("'") for p in parts if p.strip()]
            return ", ".join(parts)
        return "" if v is None else str(v)

    def detect_format(item: dict) -> str:
        # Prefer explicit fields if present
        for key in ("format", "filetype", "container", "encoding", "format_name"):
            val = item.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

        # Fall back to parsing title/name for common tokens
        name = (item.get("title") or item.get("name") or "")
        # Look for tokens anywhere (including [MP3], (M4B), etc.)
        tokens = re.findall(r'(?i)\b(mp3|m4b|flac|aac|ogg|opus|wav|alac|ape|epub|pdf|mobi|azw3|cbz|cbr)\b', name)
        if tokens:
            # Deduplicate, preserve order, uppercase
            uniq = list(dict.fromkeys(t.upper() for t in tokens))
            return "/".join(uniq)

        return ""

    out = []
    for item in raw.get("data", []):
        out.append({
            "id": item.get("id") or item.get("tid"),
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

async def qb_login(client: httpx.AsyncClient):
    r = await client.post(
        f"{QB_URL}/api/v2/auth/login",
        data={"username": QB_USER, "password": QB_PASS},
        timeout=20,
    )
    # qBittorrent returns 200 with text "Ok." on success
    if r.status_code != 200 or "Ok" not in r.text:
        raise HTTPException(status_code=502, detail=f"qB login failed: {r.status_code} {r.text[:120]}")
        

class AddBody(BaseModel):
    id: str
    title: str
    dl: str | None = None

@app.post("/add")
async def add_to_qb(body: AddBody):
    # Construct candidates
    direct_url = f"{MAM_BASE}/tor/download.php/{body.dl}" if body.dl else None
    # Cookie-authenticated fallbacks by ID (try multiple common patterns)
    id_candidates = [
        f"{MAM_BASE}/tor/download.php?id={body.id}",
        f"{MAM_BASE}/tor/download.php?tid={body.id}",
    ]

    async with httpx.AsyncClient(timeout=60) as client:
        # 1) Login to qB
        await qb_login(client)

        # 2) If we have a cookie-less direct URL, try that first
        if direct_url:
            form = {"urls": direct_url, "tags": QB_TAGS}
            if QB_SAVEPATH:
                form["savepath"] = QB_SAVEPATH
            r = await client.post(f"{QB_URL}/api/v2/torrents/add", data=form)
            if r.status_code == 200:
                # record success
                with engine.begin() as cx:
                    cx.execute(text("""
                        INSERT INTO history (mam_id, title, dl, qb_status, qb_hash, added_at)
                        VALUES (:mam_id, :title, :dl, :qb_status, :qb_hash, :added_at)
                    """), {
                        "mam_id": body.id, "title": body.title, "dl": body.dl or "",
                        "qb_status": "added", "qb_hash": None,
                        "added_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                return {"ok": True}
            # fall through to cookie fetch if direct URL refused

        # 3) Fetch the .torrent with Cookie and upload to qB
        # Build browser-y headers for MAM fetch
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
        data = {"tags": QB_TAGS}
        if QB_SAVEPATH:
            data["savepath"] = QB_SAVEPATH

        r = await client.post(f"{QB_URL}/api/v2/torrents/add", data=data, files=files)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"qB add (upload) failed: {r.status_code} {r.text[:160]}")

        # record success
        with engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO history (mam_id, title, dl, qb_status, qb_hash, added_at)
                VALUES (:mam_id, :title, :dl, :qb_status, :qb_hash, :added_at)
            """), {
                "mam_id": body.id, "title": body.title, "dl": body.dl or "",
                "qb_status": "added", "qb_hash": None,
                "added_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            })

    return {"ok": True}
    
    
@app.get("/history")
def history():
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT id, mam_id, title, dl, added_at, qb_status, qb_hash
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