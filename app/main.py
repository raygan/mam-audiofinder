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
        "ALTER TABLE history ADD COLUMN narrator TEXT",
        "ALTER TABLE history ADD COLUMN size     INTEGER"
    ):
        try:
            cx.execute(text(ddl))
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
    size: int | None = None  # bytes if provided

@app.post("/add")
async def add_to_qb(body: AddBody):
    mam_id = ("" if body.id is None else str(body.id)).strip()
    title = (body.title or "").strip()
    author = (body.author or "").strip()
    narrator = (body.narrator or "").strip()
    dl = (body.dl or "").strip()
    size = body.size if isinstance(body.size, int) else None

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
            form = {"urls": direct_url}
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
                        INSERT INTO history (mam_id, title, author, narrator, dl, qb_status, qb_hash, added_at, size)
                        VALUES (:mam_id, :title, :author, :narrator, :dl, :qb_status, :qb_hash, :added_at, :size)
                    """), {
                        "mam_id": mam_id, "title": title, "author": author, "narrator": narrator,
                        "dl": dl, "qb_status": "added", "qb_hash": qb_hash,
                        "added_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        "size": size,
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
        data = {}
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
                INSERT INTO history (mam_id, title, author, narrator, dl, qb_status, qb_hash, added_at, size)
                VALUES (:mam_id, :title, :author, :narrator, :dl, :qb_status, :qb_hash, :added_at, :size)
            """), {
                "mam_id": mam_id, "title": title, "author": author, "narrator": narrator,
                "dl": dl, "qb_status": "added", "qb_hash": qb_hash,
                "added_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "size": size,
            })

    return {"ok": True}

# ---------------------------- History ----------------------------
@app.get("/history")
def history():
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT id, mam_id, title, author, narrator, dl, qb_hash, added_at, qb_status, size
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