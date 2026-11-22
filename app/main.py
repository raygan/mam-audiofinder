"""Routes. Logic lives in flat modules: config, db, mam (the only MAM
traffic), qb, importer. See AGENTS.md."""
import hashlib, logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import db, importer, mam, qb
from config import settings, load_json_config, save_json_config, is_setup_disabled, needs_setup, apply_umask

log = logging.getLogger("mam-audiofinder")
APP_DIR = Path(__file__).resolve().parent

apply_umask()
db.migrate()

# ---------------------------- Setup ----------------------------
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
UPSTREAM_FAILED = qb.UPSTREAM_FAILED

@asynccontextmanager
async def lifespan(_app):
    # uvicorn attaches its log handlers after import; cover those too.
    mam.install_log_redaction()
    yield

app = FastAPI(title="MAM Book Finder", version=mam.APP_VERSION, lifespan=lifespan)

app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")
# Appended to static URLs so proxies (e.g. Cloudflare) don't serve stale JS
# after a rebuild: a short hash of the JS files, so it changes whenever they do.
def _asset_version() -> str:
    h = hashlib.sha256()
    for f in sorted((APP_DIR / "static").glob("*.js")):
        h.update(f.read_bytes())
    return h.hexdigest()[:10]

templates.env.globals["asset_version"] = _asset_version()

mam.install_log_redaction()

@app.exception_handler(qb.QbError)
async def qb_error_handler(request: Request, exc: qb.QbError):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status)

@app.exception_handler(importer.ImportFailed)
async def import_error_handler(request: Request, exc: importer.ImportFailed):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status)

@app.exception_handler(mam.MamError)
async def mam_error_handler(request: Request, exc: mam.MamError):
    # Fail closed: surface the reason, never retry, never fall back.
    # 424, not 502: Cloudflare replaces origin 502 bodies with its own page.
    status = 400 if isinstance(exc, mam.MamEndpointNotAllowed) else UPSTREAM_FAILED
    detail = mam.redact(str(exc))
    if isinstance(exc, mam.MamAuthError):
        detail += ". Update the mam_id cookie in Setup."
    log.warning("MAM request stopped (%s): %s", type(exc).__name__, detail)
    return JSONResponse({"detail": detail, "error": type(exc).__name__}, status_code=status)

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    setup_enabled = not is_setup_disabled()
    if needs_setup() and setup_enabled:
        return templates.TemplateResponse(request, "setup.html", setup_context(request))
    return templates.TemplateResponse(request, "index.html", {"request": request, "setup_enabled": setup_enabled})

@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    if is_setup_disabled():
        raise HTTPException(status_code=404, detail="Not found")
    return templates.TemplateResponse(request, "setup.html", setup_context(request))

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
        save_json_config(cfg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write config: {e}")

    settings.reload()
    return {"ok": True}

# ---------------------------- Search ----------------------------
@app.post("/search")
async def search(payload: dict):
    if not settings.MAM_COOKIE:
        raise HTTPException(status_code=500, detail="MAM_COOKIE not set on server")

    # Only text, sortType, perpage and media are taken from the client;
    # mam.search builds the request and the allowlist guard validates it.
    tor = payload.get("tor") or {}
    if not isinstance(tor, dict):
        raise HTTPException(status_code=400, detail="tor must be an object")
    text_q = tor.get("text") or ""
    if not isinstance(text_q, str):
        raise HTTPException(status_code=400, detail="tor.text must be a string")

    media = payload.get("media") or "audiobook"
    if not isinstance(media, str) or media not in mam.MEDIA_SEARCH:
        raise HTTPException(status_code=400, detail="media must be audiobook, ebook or both")

    result = await mam.search(
        settings.MAM_COOKIE,
        text=text_q,
        media=media,
        sort_type=tor.get("sortType") or "default",
        perpage=payload.get("perpage", 25),
    )
    return JSONResponse(result)

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

    if not mam_id:
        # Both documented download forms need ?tid=<id>.
        raise HTTPException(status_code=400, detail="Missing MAM torrent id")

    qb_hash = await qb.add_from_mam(mam_id, dl=dl, title=title)
    db.record_history(mam_id, title, author, narrator, dl, qb_hash)
    return {"ok": True}

# ---------------------------- History ----------------------------
@app.get("/history")
def history():
    return {"items": db.list_history()}

@app.delete("/history/{row_id}")
def delete_history(row_id: int):
    db.delete_history(row_id)
    return {"ok": True}

# ---------------------------- List Importable ----------------------------
@app.get("/qb/torrents")
async def qb_torrents():
    # completed in our category
    return {"items": await qb.completed_torrents(settings.QB_CATEGORY)}

# ---------------------------- Perform Import ----------------------------
class ImportBody(BaseModel):
    author: str
    title: str
    hash: str
    history_id: int | None = None

@app.post("/import")
async def do_import(body: ImportBody):
    h = body.hash
    src_root = Path(importer.map_qb_path(await qb.content_path(h), settings.QB_PATH_MAP))

    # Destination: /library/Author/Title[/...]; file copying runs off the event loop.
    dest_dir = await run_in_threadpool(
        importer.import_audiobook, src_root, body.author, body.title, settings.LIB_DIR, settings.IMPORT_MODE)

    # post-import: clear or change category so it disappears from our list
    if h and settings.QB_URL:
        await qb.set_category_best_effort(h, settings.QB_POSTIMPORT_CATEGORY)

    db.mark_imported(body.history_id, h)
    return {"ok": True, "dest": str(dest_dir)}
