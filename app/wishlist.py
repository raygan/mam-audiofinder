"""Wishlist: saved MAM searches that are re-checked later (ROADMAP Phase 2).

A wishlist item is a saved MAM query, never a book record from elsewhere.
Each check is one documented JSON search via mam.search(); a result is a new
match only if it isn't already seen for the item, isn't in History, and MAM
doesn't mark it my_snatched. Every wishlist search, manual or scheduled,
counts toward WISHLIST_MAX_REQUESTS_PER_DAY, and only one runs at a time.
"""
import asyncio, json, logging, random
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

import db
import mam
import notify
from config import settings, MEDIA_TYPES

log = logging.getLogger("mam-audiofinder")

MEDIA = tuple(mam.MEDIA_SEARCH)          # audiobook | ebook | both
MODES = ("notify", "auto")
USER_STATUSES = ("active", "paused", "done")  # "matched" is set by checks
CHECK_PERPAGE = 25
TIME_FMT = "%Y-%m-%d %H:%M:%S"

# One wishlist MAM request in flight at most (manual checks and the scheduler).
_mam_lock = asyncio.Lock()


class WishlistError(Exception):
    def __init__(self, detail: str, status: int = 400):
        self.detail = detail
        self.status = status
        super().__init__(detail)


class WishlistNotFound(WishlistError):
    def __init__(self, item_id):
        super().__init__(f"Wishlist item {item_id} not found", status=404)


class WishlistCapReached(WishlistError):
    def __init__(self, cap: int):
        super().__init__(f"Daily wishlist search limit reached ({cap} in the last 24 hours); try again later",
                         status=429)


# ---------------------------- time ----------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(TIME_FMT)


def next_check_after(dt: datetime, hours: int) -> datetime:
    """dt + interval with +-10% jitter, so checks don't line up."""
    return dt + timedelta(hours=hours * random.uniform(0.9, 1.1))


# ---------------------------- validation ----------------------------
def media_types_of(media: str) -> list[str]:
    return list(MEDIA_TYPES) if media == "both" else [media]


def validate_filters(f) -> dict:
    """Only fields present in real MAM results. Empty means no filtering."""
    if f in (None, ""):
        return {}
    if not isinstance(f, dict):
        raise WishlistError("filters must be an object")
    unknown = set(f) - {"formats", "min_seeders", "exclude", "lang_code"}
    if unknown:
        raise WishlistError(f"Unknown filter(s): {', '.join(sorted(unknown))}")
    out = {}
    if f.get("formats"):
        if not isinstance(f["formats"], list) or not all(isinstance(x, str) for x in f["formats"]):
            raise WishlistError("filters.formats must be a list of formats, e.g. [\"epub\", \"m4b\"]")
        out["formats"] = sorted({x.strip().lower().lstrip(".") for x in f["formats"] if x.strip()})
    if f.get("min_seeders") not in (None, "", 0):
        try:
            n = int(f["min_seeders"])
        except (TypeError, ValueError):
            raise WishlistError("filters.min_seeders must be a number") from None
        if n < 0:
            raise WishlistError("filters.min_seeders can't be negative")
        if n:
            out["min_seeders"] = n
    if f.get("exclude"):
        if not isinstance(f["exclude"], list) or not all(isinstance(x, str) for x in f["exclude"]):
            raise WishlistError("filters.exclude must be a list of words")
        out["exclude"] = [x.strip().lower() for x in f["exclude"] if x.strip()]
    if f.get("lang_code"):
        if not isinstance(f["lang_code"], str):
            raise WishlistError("filters.lang_code must be a language code, e.g. ENG")
        out["lang_code"] = f["lang_code"].strip().upper()
    return {k: v for k, v in out.items() if v}


def passes_filters(r: dict, f: dict) -> bool:
    if f.get("formats"):
        have = {t for t in str(r.get("format") or "").lower().split("/") if t}
        if not have & set(f["formats"]):
            return False
    if f.get("min_seeders"):
        try:
            if int(r.get("seeders") or 0) < f["min_seeders"]:
                return False
        except (TypeError, ValueError):
            return False
    if f.get("exclude"):
        hay = f"{r.get('title') or ''} {r.get('series') or ''}".lower()
        if any(w in hay for w in f["exclude"]):
            return False
    if f.get("lang_code") and str(r.get("lang_code") or "").upper() != f["lang_code"]:
        return False
    return True


def _validate_query(q) -> str:
    if not isinstance(q, str) or not q.strip():
        raise WishlistError("query is required")
    if len(q) > 200:
        raise WishlistError("query is too long")
    return q.strip()


def _validate_srch_in(srch_in, media: str) -> list[str]:
    if not srch_in:
        return list(mam.MEDIA_SEARCH[media][1])
    if not isinstance(srch_in, list) or any(x not in mam.SRCH_IN for x in srch_in):
        raise WishlistError(f"srch_in values must be from {sorted(mam.SRCH_IN)}")
    return list(dict.fromkeys(srch_in))


def _validate_interval(v):
    if v in (None, ""):
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise WishlistError("check_interval_hours must be a whole number of hours") from None
    if n < 1:
        raise WishlistError("check_interval_hours must be at least 1")
    return n


# ---------------------------- storage ----------------------------
def _decode(row) -> dict:
    d = dict(row)
    for key, empty in (("srch_in", []), ("filters", {}), ("fulfilled", [])):
        try:
            d[key] = json.loads(d.get(key) or "null") or empty
        except ValueError:
            d[key] = empty
    return d


def _match_counts(cx) -> dict[int, int]:
    rows = cx.execute(text("""SELECT wishlist_id, COUNT(*) FROM wishlist_seen
                              WHERE is_match = 1 AND dismissed = 0 GROUP BY wishlist_id"""))
    return {r[0]: r[1] for r in rows}


def get(item_id: int) -> dict:
    with db.engine.begin() as cx:
        row = cx.execute(text("SELECT * FROM wishlist WHERE id = :id"), {"id": item_id}).mappings().first()
        if row is None:
            raise WishlistNotFound(item_id)
        d = _decode(row)
        d["match_count"] = _match_counts(cx).get(item_id, 0)
    return d


def list_items() -> list[dict]:
    with db.engine.begin() as cx:
        rows = cx.execute(text("SELECT * FROM wishlist ORDER BY id DESC")).mappings().all()
        counts = _match_counts(cx)
    out = []
    for r in rows:
        d = _decode(r)
        d["match_count"] = counts.get(d["id"], 0)
        out.append(d)
    return out


def create(query, media="audiobook", srch_in=None, sort_type="default", label=None, filters=None,
           mode="notify", check_interval_hours=None, seen=None) -> dict:
    """Save a search. `seen` are MAM ids already on screen: they become the
    baseline, so only later uploads count. No MAM request is made."""
    query = _validate_query(query)
    if media not in MEDIA:
        raise WishlistError("media must be audiobook, ebook or both")
    srch_in = _validate_srch_in(srch_in, media)
    if sort_type not in mam.SORT_TYPES:
        raise WishlistError("sort_type not allowed")
    if mode not in MODES:
        raise WishlistError("mode must be notify or auto")
    filters = validate_filters(filters)
    interval = _validate_interval(check_interval_hours)
    seen_ids = [str(x) for x in (seen or []) if str(x).isdigit()]
    if label is not None and not isinstance(label, str):
        raise WishlistError("label must be text")

    now = _now()
    with db.engine.begin() as cx:
        item_id = cx.execute(text("""
            INSERT INTO wishlist (query, srch_in, media, sort_type, label, filters, mode, status,
                                  fulfilled, created_at, next_check_at, check_interval_hours)
            VALUES (:query, :srch_in, :media, :sort_type, :label, :filters, :mode, 'active',
                    '[]', :created_at, :next_check_at, :interval)
        """), {
            "query": query, "srch_in": json.dumps(srch_in), "media": media, "sort_type": sort_type,
            "label": (label or "").strip() or None, "filters": json.dumps(filters), "mode": mode,
            "created_at": _fmt(now),
            "next_check_at": _fmt(next_check_after(now, interval or settings.WISHLIST_INTERVAL_HOURS)),
            "interval": interval,
        }).lastrowid
        for mid in dict.fromkeys(seen_ids):
            cx.execute(text("""INSERT OR IGNORE INTO wishlist_seen (wishlist_id, mam_id, first_seen_at, is_match)
                               VALUES (:w, :m, :t, 0)"""), {"w": item_id, "m": mid, "t": _fmt(now)})
    return get(item_id)


EDITABLE = {"label", "filters", "mode", "status", "check_interval_hours", "query", "srch_in", "sort_type"}


def update(item_id: int, fields: dict) -> dict:
    item = get(item_id)
    unknown = set(fields) - EDITABLE
    if unknown:
        raise WishlistError(f"Can't change: {', '.join(sorted(unknown))}")
    sets = {}
    if "label" in fields:
        if fields["label"] is not None and not isinstance(fields["label"], str):
            raise WishlistError("label must be text")
        sets["label"] = (fields["label"] or "").strip() or None
    if "filters" in fields:
        sets["filters"] = json.dumps(validate_filters(fields["filters"]))
    if "mode" in fields:
        if fields["mode"] not in MODES:
            raise WishlistError("mode must be notify or auto")
        sets["mode"] = fields["mode"]
    if "status" in fields:
        if fields["status"] not in USER_STATUSES:
            raise WishlistError("status must be active, paused or done")
        sets["status"] = fields["status"]
    if "check_interval_hours" in fields:
        sets["check_interval_hours"] = _validate_interval(fields["check_interval_hours"])
    if "query" in fields:
        sets["query"] = _validate_query(fields["query"])
    if "srch_in" in fields:
        sets["srch_in"] = json.dumps(_validate_srch_in(fields["srch_in"], item["media"]))
    if "sort_type" in fields:
        if fields["sort_type"] not in mam.SORT_TYPES:
            raise WishlistError("sort_type not allowed")
        sets["sort_type"] = fields["sort_type"]
    if sets:
        cols = ", ".join(f"{k} = :{k}" for k in sets)
        with db.engine.begin() as cx:
            cx.execute(text(f"UPDATE wishlist SET {cols} WHERE id = :id"), {**sets, "id": item_id})
    return get(item_id)


def delete(item_id: int):
    get(item_id)
    with db.engine.begin() as cx:
        cx.execute(text("DELETE FROM wishlist_seen WHERE wishlist_id = :id"), {"id": item_id})
        cx.execute(text("DELETE FROM wishlist WHERE id = :id"), {"id": item_id})


def matches(item_id: int, include_dismissed: bool = False) -> list[dict]:
    get(item_id)
    with db.engine.begin() as cx:
        rows = cx.execute(text(f"""
            SELECT mam_id, first_seen_at, dismissed, result FROM wishlist_seen
            WHERE wishlist_id = :id AND is_match = 1 {"" if include_dismissed else "AND dismissed = 0"}
            ORDER BY first_seen_at DESC, mam_id DESC
        """), {"id": item_id}).mappings().all()
    out = []
    for r in rows:
        try:
            result = json.loads(r["result"] or "{}")
        except ValueError:
            result = {}
        out.append({"mam_id": r["mam_id"], "first_seen_at": r["first_seen_at"],
                    "dismissed": bool(r["dismissed"]), "result": result})
    return out


def dismiss(item_id: int, mam_id: str):
    get(item_id)
    with db.engine.begin() as cx:
        n = cx.execute(text("""UPDATE wishlist_seen SET dismissed = 1
                               WHERE wishlist_id = :w AND mam_id = :m AND is_match = 1"""),
                       {"w": item_id, "m": str(mam_id)}).rowcount
    if not n:
        raise WishlistError(f"No match {mam_id} on item {item_id}", status=404)


def mark_added(item_id: int, mam_id: str, media_type: str) -> dict:
    """After a match is added to qB: it's reviewed, that media type is
    fulfilled, and the item is done once all its media types are."""
    item = get(item_id)
    fulfilled = list(dict.fromkeys(item["fulfilled"] + [media_type]))
    done = set(media_types_of(item["media"])) <= set(fulfilled)
    with db.engine.begin() as cx:
        cx.execute(text("UPDATE wishlist_seen SET dismissed = 1 WHERE wishlist_id = :w AND mam_id = :m"),
                   {"w": item_id, "m": str(mam_id)})
        cx.execute(text("UPDATE wishlist SET fulfilled = :f, status = CASE WHEN :done THEN 'done' ELSE status END "
                        "WHERE id = :id"), {"f": json.dumps(fulfilled), "done": done, "id": item_id})
    return get(item_id)


def unreviewed_match_count() -> int:
    with db.engine.begin() as cx:
        return int(cx.execute(text("""SELECT COUNT(*) FROM wishlist_seen s JOIN wishlist w ON w.id = s.wishlist_id
                                      WHERE s.is_match = 1 AND s.dismissed = 0""")).scalar() or 0)


# ---------------------------- daily cap ----------------------------
def requests_last_24h(now: datetime | None = None) -> int:
    since = _fmt((now or _now()) - timedelta(hours=24))
    with db.engine.begin() as cx:
        return int(cx.execute(text("SELECT COUNT(*) FROM mam_request_log WHERE at > :s"), {"s": since}).scalar() or 0)


def _log_request(kind: str, now: datetime):
    with db.engine.begin() as cx:
        cx.execute(text("INSERT INTO mam_request_log (at, kind) VALUES (:at, :k)"), {"at": _fmt(now), "k": kind})


# ---------------------------- checking ----------------------------
async def check(item_id: int, cookie: str, trigger: str = "manual", now: datetime | None = None) -> dict:
    """Run one wishlist search for an item and record new matches.

    Raises WishlistCapReached before sending if the daily cap is used up, and
    re-raises any mam.MamError after recording it on the item (the caller
    decides whether to halt; it never retries).
    """
    async with _mam_lock:
        now = now or _now()
        item = get(item_id)
        if item["status"] == "done":
            raise WishlistError("This item is done; set it back to active to check it again", status=409)
        cap = settings.WISHLIST_MAX_REQUESTS_PER_DAY
        if requests_last_24h(now) >= cap:
            raise WishlistCapReached(cap)

        pending = [m for m in media_types_of(item["media"]) if m not in item["fulfilled"]]
        if not pending:
            raise WishlistError("Every media type on this item is already fulfilled", status=409)
        search_media = "both" if len(pending) == 2 else pending[0]
        interval = item["check_interval_hours"] or settings.WISHLIST_INTERVAL_HOURS

        # The attempt counts toward the cap whether or not it succeeds.
        _log_request(f"wishlist:{trigger}", now)
        try:
            res = await mam.search(
                cookie, text=item["query"], media=search_media, srch_in=item["srch_in"],
                sort_type=item["sort_type"], perpage=CHECK_PERPAGE, search_type="active",
                # Only torrents added since the item was saved (keeps replies small).
                start_date=item["created_at"][:10],
            )
        except mam.MamError as e:
            with db.engine.begin() as cx:
                cx.execute(text("UPDATE wishlist SET last_checked_at = :t, last_error = :e WHERE id = :id"),
                           {"t": _fmt(now), "e": mam.redact(str(e))[:300], "id": item_id})
            raise

        results = [r for r in res["results"] if r.get("id")]
        ids = [r["id"] for r in results]
        new_matches = []
        with db.engine.begin() as cx:
            seen = {r[0] for r in cx.execute(text("SELECT mam_id FROM wishlist_seen WHERE wishlist_id = :w"),
                                             {"w": item_id})}
            in_history = set()
            if ids:
                params = {f"m{i}": v for i, v in enumerate(ids)}
                in_history = {r[0] for r in cx.execute(
                    text(f"SELECT mam_id FROM history WHERE mam_id IN ({', '.join(':' + k for k in params)})"),
                    params)}
            for r in results:
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                is_match = (r.get("media_type") in pending and r["id"] not in in_history
                            and not r.get("my_snatched") and passes_filters(r, item["filters"]))
                cx.execute(text("""INSERT INTO wishlist_seen (wishlist_id, mam_id, first_seen_at, is_match, result)
                                   VALUES (:w, :m, :t, :is_match, :result)"""), {
                    "w": item_id, "m": r["id"], "t": _fmt(now), "is_match": int(is_match),
                    "result": json.dumps(r) if is_match else None,
                })
                if is_match:
                    new_matches.append(r)
            cx.execute(text("""UPDATE wishlist SET last_checked_at = :t, next_check_at = :n, last_error = NULL,
                                   status = CASE WHEN :matched AND status = 'active' THEN 'matched' ELSE status END
                               WHERE id = :id"""), {
                "t": _fmt(now), "n": _fmt(next_check_after(now, interval)),
                "matched": bool(new_matches), "id": item_id,
            })
        updated = get(item_id)
        if new_matches:
            log.info("Wishlist item %s: %d new match(es)", item_id, len(new_matches))
            # Best effort: a failed notification never fails the check.
            await notify.wishlist_matches(updated, new_matches)
        return {"item": updated, "new_matches": new_matches}
