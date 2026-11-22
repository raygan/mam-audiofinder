"""Wishlist scheduler (ROADMAP Phase 2, rule 7): opt-in and conservative.

Runs only when WISHLIST_SCHEDULER_ENABLED is true, as ONE in-process
asyncio task (the app must run as a single worker). It re-checks due
wishlist items through wishlist.check(), which holds the shared lock, so at
most one wishlist MAM request is ever in flight. Between MAM requests it
waits a random 30-90 s (never less than 30 s), and it never exceeds
WISHLIST_MAX_REQUESTS_PER_DAY (shared with manual checks).

Fail closed: any MAM error halts all scheduled checks, records why,
notifies once, and nothing runs again until the user resumes. The halt is
stored in the database, so a restart doesn't clear it.
"""
import asyncio, json, logging, random
from datetime import datetime, timezone

from sqlalchemy import text

import db
import mam
import notify
import qb
import wishlist
from config import settings

log = logging.getLogger("mam-audiofinder")
# uvicorn's logger is shown at INFO (the app logger only shows warnings).
info_log = logging.getLogger("uvicorn.error")

MIN_DELAY_SECONDS = 30  # floor for the gap between scheduled MAM requests
HALT_KEY = "scheduler_halted"
AUDIO_FORMAT_PREFERENCE = ("m4b", "mp3", "m4a", "flac", "aac", "ogg", "opus")

_task: asyncio.Task | None = None


# ---------------------------- halt state ----------------------------
def halted() -> dict | None:
    with db.engine.begin() as cx:
        v = cx.execute(text("SELECT value FROM app_state WHERE key = :k"), {"k": HALT_KEY}).scalar()
    if not v:
        return None
    try:
        return json.loads(v)
    except ValueError:
        return {"reason": "unknown", "at": ""}


async def halt(reason: str) -> bool:
    """Stop all scheduled checks. Notifies only on the first halt; returns
    True if this call halted it (False if it was already halted)."""
    reason = mam.redact(reason)[:300]
    state = json.dumps({"reason": reason, "at": wishlist._fmt(datetime.now(timezone.utc))})
    with db.engine.begin() as cx:
        inserted = cx.execute(text("INSERT OR IGNORE INTO app_state (key, value) VALUES (:k, :v)"),
                              {"k": HALT_KEY, "v": state}).rowcount
    if not inserted:
        return False
    log.warning("Wishlist scheduler halted: %s", reason)
    await notify.send("halt", "Book Finder: wishlist checks stopped",
                      f"{reason}\nFix the cause, then press Resume on the Wishlist page.")
    return True


def resume():
    with db.engine.begin() as cx:
        cx.execute(text("DELETE FROM app_state WHERE key = :k"), {"k": HALT_KEY})
    info_log.info("Wishlist scheduler resumed by the user")


def delay_bounds() -> tuple[float, float]:
    lo = max(MIN_DELAY_SECONDS, settings.WISHLIST_DELAY_MIN_SECONDS)
    hi = max(lo, settings.WISHLIST_DELAY_MAX_SECONDS)
    return lo, hi


def due_items(now: datetime) -> list[dict]:
    with db.engine.begin() as cx:
        ids = [r[0] for r in cx.execute(text("""
            SELECT id FROM wishlist
            WHERE status IN ('active', 'matched') AND next_check_at IS NOT NULL AND next_check_at <= :now
            ORDER BY next_check_at, id
        """), {"now": wishlist._fmt(now)})]
    return [wishlist.get(i) for i in ids]


def next_due() -> str | None:
    with db.engine.begin() as cx:
        return cx.execute(text("""SELECT MIN(next_check_at) FROM wishlist
                                  WHERE status IN ('active', 'matched')""")).scalar()


def status() -> dict:
    h = halted()
    if not settings.WISHLIST_SCHEDULER_ENABLED:
        state = "disabled"
    elif h:
        state = "halted"
    else:
        state = "running" if _task is not None and not _task.done() else "stopped"
    return {
        "state": state,
        "enabled": settings.WISHLIST_SCHEDULER_ENABLED,
        "halted": h,
        "requests_last_24h": wishlist.requests_last_24h(),
        "max_requests_per_day": settings.WISHLIST_MAX_REQUESTS_PER_DAY,
        "interval_hours": settings.WISHLIST_INTERVAL_HOURS,
        "next_due": next_due(),
    }


# ---------------------------- auto mode ----------------------------
def _rank(r: dict) -> tuple:
    pref = settings.EBOOK_FORMAT_PREFERENCE if r.get("media_type") == "ebook" else AUDIO_FORMAT_PREFERENCE
    fmts = [t for t in str(r.get("format") or "").lower().split("/") if t]
    pos = min((pref.index(f) for f in fmts if f in pref), default=len(pref))
    try:
        seeders = int(r.get("seeders") or 0)
    except (TypeError, ValueError):
        seeders = 0
    return (pos, -seeders)


def best_matches(matches: list[dict], wanted: list[str]) -> list[dict]:
    """One pick per wanted media type: preferred format first, then seeders."""
    picks = []
    for media in wanted:
        cands = [m for m in matches if m.get("media_type") == media]
        if cands:
            picks.append(min(cands, key=_rank))
    return picks


async def auto_grab(item: dict, new_matches: list[dict]) -> list[dict]:
    wanted = [m for m in wishlist.media_types_of(item["media"]) if m not in item["fulfilled"]]
    added = []
    for r in best_matches(new_matches, wanted):
        try:
            qb_hash = await qb.add_from_mam(r["id"], dl=r.get("dl") or "", title=r.get("title") or "",
                                            media_type=r["media_type"])
        except qb.QbDuplicate:
            qb_hash = None  # already in qB: still counts as fulfilled
        except qb.QbError as e:
            log.warning("Auto-grab of %s for wishlist item %s failed: %s", r["id"], item["id"], e.detail)
            continue  # left as a match for the user to review
        db.record_history(r["id"], r.get("title") or "", r.get("author_info") or "", r.get("narrator_info") or "",
                          r.get("dl") or "", qb_hash, r["media_type"])
        wishlist.mark_added(item["id"], r["id"], r["media_type"])
        await notify.send("auto_grab", f"Auto-grabbed: {r.get('title')}",
                          f"From wishlist “{item.get('label') or item['query']}” ({r.get('format') or r['media_type']}).")
        added.append(r)
    return added


# ---------------------------- the loop ----------------------------
async def run_once(cookie: str, now_fn=None, sleep=asyncio.sleep, rand=random.uniform) -> int:
    """Check every due item, one MAM request at a time. Returns how many
    requests were made. Stops on halt, on the daily cap, or when nothing is due."""
    now_fn = now_fn or (lambda: datetime.now(timezone.utc))
    made = 0
    attempted: set[int] = set()
    while True:
        if halted() or not cookie:
            break
        if wishlist.requests_last_24h(now_fn()) >= settings.WISHLIST_MAX_REQUESTS_PER_DAY:
            break  # wait for the rolling window; not an error
        due = [i for i in due_items(now_fn()) if i["id"] not in attempted]
        if not due:
            break
        item = due[0]
        attempted.add(item["id"])
        if made:
            await sleep(rand(*delay_bounds()))  # gap between scheduled MAM requests
        try:
            res = await wishlist.check(item["id"], cookie, trigger="scheduler", now=now_fn())
        except wishlist.WishlistCapReached:
            break
        except wishlist.WishlistError as e:
            log.info("Scheduler skipped wishlist item %s: %s", item["id"], e.detail)
            continue
        except mam.MamError as e:
            made += 1
            await halt(f"{type(e).__name__}: {e}")
            break
        made += 1
        if item["mode"] == "auto" and res["new_matches"]:
            await auto_grab(res["item"], res["new_matches"])
    return made


async def loop(sleep=asyncio.sleep, rand=random.uniform):
    info_log.info("Wishlist scheduler started: every %sh, max %s wishlist searches/day, %s-%ss between requests",
             settings.WISHLIST_INTERVAL_HOURS, settings.WISHLIST_MAX_REQUESTS_PER_DAY, *delay_bounds())
    while True:
        try:
            if settings.WISHLIST_SCHEDULER_ENABLED:
                await run_once(settings.MAM_COOKIE, sleep=sleep, rand=rand)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A bug, not a MAM error: stop scheduled traffic rather than spin.
            log.exception("Wishlist scheduler crashed")
            await halt("The scheduler hit an internal error; see the app logs")
        # Also keeps at least the minimum gap after the last request of a run.
        await sleep(rand(*delay_bounds()))


def start() -> asyncio.Task | None:
    global _task
    if not settings.WISHLIST_SCHEDULER_ENABLED:
        info_log.info("Wishlist scheduler is disabled (WISHLIST_SCHEDULER_ENABLED=false); only manual checks run")
        return None
    if _task is None or _task.done():
        _task = asyncio.get_running_loop().create_task(loop())
    return _task


async def stop():
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except (asyncio.CancelledError, Exception):
            pass
        _task = None
