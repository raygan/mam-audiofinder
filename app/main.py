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

import db, importer, mam, notify, qb, wishlist
from config import settings, load_json_config, save_json_config, is_setup_disabled, needs_setup, apply_umask, MEDIA_TYPES

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
        "ebook_ingest_dir": settings.EBOOK_INGEST_DIR,
        "notify_webhook_url": settings.NOTIFY_WEBHOOK_URL,
        "notify_format": settings.NOTIFY_FORMAT,
        "notify_has_token": bool(settings.NOTIFY_TOKEN),  # never the token itself
        "notify_click_url": settings.NOTIFY_CLICK_URL,
        "notify_on_import": settings.NOTIFY_ON_IMPORT,
        "qb_prefix": qb_prefix,
        "app_prefix": app_prefix,
    }

class SetupPayload(BaseModel):
    mam_cookie: str | None = None
    qb_url: str | None = None
    qb_user: str | None = None
    qb_pass: str | None = None
    lib_dir: str | None = None
    ebook_ingest_dir: str | None = None
    notify_webhook_url: str | None = None
    notify_format: str | None = None
    notify_token: str | None = None   # blank keeps the saved token
    notify_clear_token: bool = False
    notify_click_url: str | None = None
    notify_on_import: bool | None = None
    qb_prefix: str | None = None
    app_prefix: str | None = None

# ---------------------------- App ----------------------------
UPSTREAM_FAILED = qb.UPSTREAM_FAILED

@asynccontextmanager
async def lifespan(_app):
    # uvicorn attaches its log handlers after import; cover those too.
    mam.install_log_redaction()
    if settings.EBOOK_INGEST_DIR:
        problem = importer.ingest_dir_problem(settings.EBOOK_INGEST_DIR, write_test=True)
        if problem:
            log.warning("Ebook import disabled: %s", problem)
        else:
            # uvicorn's logger is shown at INFO; the app logger only shows warnings.
            logging.getLogger("uvicorn.error").info("Ebook ingest folder OK: %s", settings.EBOOK_INGEST_DIR)
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

@app.exception_handler(wishlist.WishlistError)
async def wishlist_error_handler(request: Request, exc: wishlist.WishlistError):
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
    # "ok" stays a plain liveness flag; ebook_ingest reports the ebook import folder.
    if not settings.EBOOK_INGEST_DIR:
        ingest = "not configured"
    else:
        ingest = importer.ingest_dir_problem(settings.EBOOK_INGEST_DIR) or "ok"
    return {"ok": True, "ebook_ingest": ingest}

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
    if body.ebook_ingest_dir and body.ebook_ingest_dir.strip():
        ingest = body.ebook_ingest_dir.strip().rstrip("/") or "/"
        problem = importer.ingest_dir_problem(ingest, write_test=True)
        if problem:
            raise HTTPException(status_code=400, detail=problem)
        cfg["EBOOK_INGEST_DIR"] = ingest
    if body.notify_webhook_url is not None:
        url = body.notify_webhook_url.strip()
        if url:
            problem = notify.target_problem(url)
            if problem:
                raise HTTPException(status_code=400, detail=problem)
        cfg["NOTIFY_WEBHOOK_URL"] = url
    if body.notify_format is not None:
        if body.notify_format not in notify.FORMATS:
            raise HTTPException(status_code=400, detail="notify_format must be ntfy or json")
        cfg["NOTIFY_FORMAT"] = body.notify_format
    if body.notify_clear_token:
        cfg["NOTIFY_TOKEN"] = ""
    elif body.notify_token and body.notify_token.strip():
        cfg["NOTIFY_TOKEN"] = body.notify_token.strip()
    if body.notify_click_url is not None:
        cfg["NOTIFY_CLICK_URL"] = body.notify_click_url.strip()
    if body.notify_on_import is not None:
        cfg["NOTIFY_ON_IMPORT"] = "true" if body.notify_on_import else "false"

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

@app.post("/api/notify/test")
async def notify_test():
    """Send one test notification with the saved settings (user-initiated)."""
    if is_setup_disabled():
        raise HTTPException(status_code=404, detail="Not found")
    problem = notify.target_problem(settings.NOTIFY_WEBHOOK_URL)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    ok = await notify.send("test", "Book Finder test notification", "Notifications from Book Finder are working.")
    if not ok:
        raise HTTPException(status_code=qb.UPSTREAM_FAILED, detail="The notification wasn't accepted; check the URL, token and app logs")
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
    media_type: str | None = None
    wishlist_id: int | None = None  # set when adding a wishlist match

@app.post("/add")
async def add_to_qb(body: AddBody):
    mam_id = ("" if body.id is None else str(body.id)).strip()
    title = (body.title or "").strip()
    author = (body.author or "").strip()
    narrator = (body.narrator or "").strip()
    dl = (body.dl or "").strip()

    media_type = body.media_type or "audiobook"

    if not mam_id:
        # Both documented download forms need ?tid=<id>.
        raise HTTPException(status_code=400, detail="Missing MAM torrent id")
    if media_type not in MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="media_type must be audiobook or ebook")

    qb_hash = await qb.add_from_mam(mam_id, dl=dl, title=title, media_type=media_type)
    db.record_history(mam_id, title, author, narrator, dl, qb_hash, media_type)
    if body.wishlist_id is not None:
        try:
            wishlist.mark_added(body.wishlist_id, mam_id, media_type)
        except wishlist.WishlistError as e:
            # The torrent is already in qB; don't report the add as failed.
            log.warning("Added %s but couldn't update wishlist item %s: %s", mam_id, body.wishlist_id, e.detail)
    return {"ok": True}

# ---------------------------- Wishlist ----------------------------
class WishlistCreate(BaseModel):
    query: str
    media: str = "audiobook"
    srch_in: list[str] | None = None
    sort_type: str = "default"
    label: str | None = None
    filters: dict | None = None
    mode: str = "notify"
    check_interval_hours: int | None = None
    seen: list[str | int] | None = None  # MAM ids already on screen (baseline)

@app.get("/wishlist/view", response_class=HTMLResponse)
async def wishlist_page(request: Request):
    return templates.TemplateResponse(request, "wishlist.html", {"request": request})

@app.get("/wishlist/summary")
def wishlist_summary():
    """For the search page's header indicator. Database only; never contacts MAM."""
    return {
        "unreviewed": wishlist.unreviewed_match_count(),
        "items": len(wishlist.list_items()),
        # The scheduler arrives in a later 0.9 step; nothing runs until then.
        "scheduler": "disabled",
    }

@app.get("/wishlist")
def wishlist_list():
    return {
        "items": wishlist.list_items(),
        "requests_last_24h": wishlist.requests_last_24h(),
        "max_requests_per_day": settings.WISHLIST_MAX_REQUESTS_PER_DAY,
    }

@app.post("/wishlist")
def wishlist_create(body: WishlistCreate):
    # Saving never contacts MAM; the results already on screen are the baseline.
    return wishlist.create(**body.model_dump())

@app.patch("/wishlist/{item_id}")
def wishlist_update(item_id: int, fields: dict):
    return wishlist.update(item_id, fields)

@app.delete("/wishlist/{item_id}")
def wishlist_delete(item_id: int):
    wishlist.delete(item_id)
    return {"ok": True}

@app.post("/wishlist/{item_id}/check")
async def wishlist_check(item_id: int):
    """A user-initiated wishlist search ("check now")."""
    if not settings.MAM_COOKIE:
        raise HTTPException(status_code=500, detail="MAM_COOKIE not set on server")
    return await wishlist.check(item_id, settings.MAM_COOKIE, trigger="manual")

@app.get("/wishlist/{item_id}/matches")
def wishlist_matches(item_id: int, include_dismissed: bool = False):
    return {"matches": wishlist.matches(item_id, include_dismissed)}

@app.post("/wishlist/{item_id}/matches/{mam_id}/dismiss")
def wishlist_dismiss(item_id: int, mam_id: str):
    wishlist.dismiss(item_id, mam_id)
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
async def qb_torrents(media: str = "audiobook"):
    # completed in this media type's category
    if media not in MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="media must be audiobook or ebook")
    return {"items": await qb.completed_torrents(settings.qb_category(media))}

# ---------------------------- Perform Import ----------------------------
class ImportBody(BaseModel):
    hash: str
    history_id: int | None = None
    # audiobooks
    author: str | None = None
    title: str | None = None
    # ebooks: relative paths from /import/ebook-choices
    files: list[str] | None = None

async def _content_root(h: str) -> Path:
    return Path(importer.map_qb_path(await qb.content_path(h), settings.QB_PATH_MAP))

@app.get("/import/ebook-choices")
async def ebook_choices(hash: str):
    """Ebook files in a completed torrent, grouped by book, preferred format pre-selected."""
    src_root = await _content_root(hash)
    books = await run_in_threadpool(
        importer.ebook_choices, src_root, settings.EBOOK_EXTENSIONS, settings.EBOOK_FORMAT_PREFERENCE)
    return {"books": books}

@app.post("/import")
async def do_import(body: ImportBody):
    h = body.hash
    # The History row decides the importer, not the browser.
    media_type = db.history_media_type(body.history_id, h)

    if media_type == "ebook":
        problem = importer.ingest_dir_problem(settings.EBOOK_INGEST_DIR)
        if problem:
            raise HTTPException(status_code=400, detail=problem)
        if not body.files:
            raise HTTPException(status_code=400, detail="Choose at least one file to import")
        src_root = await _content_root(h)
        # Copy only (never link/move); flat into the ebook import folder.
        copied = await run_in_threadpool(
            importer.import_ebooks, src_root, body.files, settings.EBOOK_INGEST_DIR, settings.EBOOK_EXTENSIONS)
        dest = settings.EBOOK_INGEST_DIR
        result = {"files": [p.name for p in copied]}
    else:
        author, title = (body.author or "").strip(), (body.title or "").strip()
        if not author or not title:
            raise HTTPException(status_code=400, detail="Author and title are required")
        src_root = await _content_root(h)
        # Destination: /library/Author/Title[/...]; file copying runs off the event loop.
        dest = await run_in_threadpool(
            importer.import_audiobook, src_root, author, title, settings.LIB_DIR, settings.IMPORT_MODE)
        result = {}

    # post-import: clear or change category so it disappears from our list
    if h and settings.QB_URL:
        await qb.set_category_best_effort(h, settings.postimport_category(media_type))

    db.mark_imported(body.history_id, h)
    await notify.imported((body.title or "").strip() or ", ".join(result.get("files", [])) or "torrent", media_type)
    return {"ok": True, "dest": str(dest), **result}
