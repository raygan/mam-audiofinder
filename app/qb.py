"""qBittorrent WebUI API. Shared by the HTTP routes and (later) the scheduler.

Raises QbError (and QbDuplicate) instead of HTTP errors; main.py maps them.
MAM traffic still only happens in mam.py.
"""
import logging

import httpx

import mam
from config import settings

log = logging.getLogger("mam-audiofinder")


# Not 502/504: reverse proxies such as Cloudflare replace those bodies with
# their own error page, hiding the reason from the user.
UPSTREAM_FAILED = 424


class QbError(Exception):
    """A qB request failed. `status` is the HTTP status main.py returns."""

    def __init__(self, detail: str, status: int = UPSTREAM_FAILED):
        self.detail = mam.redact(detail)
        self.status = status
        super().__init__(self.detail)


class QbDuplicate(QbError):
    def __init__(self):
        super().__init__("Already in qBittorrent", status=409)


def _fail(detail: str, status: int = UPSTREAM_FAILED) -> QbError:
    err = QbError(detail, status)
    log.warning("qB request failed: %s", err.detail)
    return err


def login_ok(r: httpx.Response) -> bool:
    """Older qB replies 200 'Ok.'; newer qB can reply 204 No Content.
    Wrong credentials are 200 'Fails.'; a banned IP is 403."""
    if r.status_code == 204:
        return True
    return r.status_code == 200 and (r.text or "").strip() == "Ok."


def add_ok(r: httpx.Response) -> bool:
    """qB < 5.x replies 200 'Ok.' / 'Fails.'. Newer versions reply with JSON
    counts, and 202 Accepted when a URL add is still pending (qB fetches it)."""
    if r.status_code not in (200, 202):
        return False
    body = (r.text or "").strip()
    if body == "Fails.":
        return False
    try:
        j = r.json()
    except ValueError:
        return True
    if isinstance(j, dict) and "failure_count" in j:
        added = int(j.get("success_count") or 0) + int(j.get("pending_count") or 0)
        return added > 0 or int(j.get("failure_count") or 0) == 0
    return True


def client(timeout: float = 30) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout)


def _url(path: str) -> str:
    return f"{settings.QB_URL}{path}"


async def login(c: httpx.AsyncClient):
    r = await c.post(_url("/api/v2/auth/login"),
                     data={"username": settings.QB_USER, "password": settings.QB_PASS},
                     timeout=20)
    if not login_ok(r):
        raise _fail(f"qB login failed: {r.status_code} {r.text[:120]}")


async def find_hash(c: httpx.AsyncClient, mam_id: str, title: str) -> str | None:
    if not mam_id:
        return None
    info = await c.get(_url("/api/v2/torrents/info"), params={"tag": f"mamid={mam_id}", "filter": "all"})
    try:
        arr = info.json()
    except Exception:
        return None
    if not isinstance(arr, list) or not arr:
        return None
    tlow = title.lower()
    for tor in arr:
        if tlow and (tor.get("name") or "").lower().startswith(tlow[:20]):
            return tor.get("hash")
    return arr[0].get("hash")


async def add_from_mam(mam_id: str, dl: str = "", title: str = "", media_type: str = "audiobook") -> str | None:
    """Add one MAM torrent to qB. Returns the qB hash if it can be found.

    With a dl hash, qB gets the documented cookie-less URL and fetches it
    itself; there is no fallback if qB rejects it. Without one, mam.py makes
    a single cookie-authenticated download and the bytes are uploaded.
    """
    if not mam_id or not mam_id.isdigit():
        # Both documented download forms need ?tid=<id>.
        raise QbError("MAM torrent id must be numeric", status=400)

    tag_list = settings.qb_tags(media_type) + [f"mamid={mam_id}"]
    form = {"category": settings.qb_category(media_type), "tags": ",".join(tag_list)}
    if settings.QB_SAVEPATH:
        form["savepath"] = settings.QB_SAVEPATH

    async with client(timeout=60) as c:
        await login(c)

        if dl:
            form["urls"] = mam.build_dl_url(dl, mam_id)
            r = await c.post(_url("/api/v2/torrents/add"), data=form)
            how = "url"
        else:
            torrent_bytes = await mam.fetch_torrent(settings.MAM_COOKIE, mam_id)
            files = {"torrents": ("mam.torrent", torrent_bytes, "application/x-bittorrent")}
            r = await c.post(_url("/api/v2/torrents/add"), data=form, files=files)
            how = "upload"
        if r.status_code == 409:
            # Newer qB answers 409 Conflict when the torrent is already in the session.
            raise QbDuplicate()
        if not add_ok(r):
            raise _fail(f"qB add ({how}) failed: {r.status_code} {r.text[:160]}")

        return await find_hash(c, mam_id, title)


async def completed_torrents(category: str) -> list[dict]:
    """Completed torrents in a category, with single-file/root info for import."""
    async with client() as c:
        await login(c)
        r = await c.get(_url("/api/v2/torrents/info"), params={"category": category, "filter": "completed"})
        if r.status_code != 200:
            raise _fail(f"qB torrent list failed: {r.status_code}")
        try:
            infos = r.json()
        except ValueError:
            infos = []
        if not isinstance(infos, list):
            infos = []

        out = []
        for t in infos:
            h = t.get("hash")
            if not h:
                continue
            # files to determine single vs multi + root
            fr = await c.get(_url("/api/v2/torrents/files"), params={"hash": h})
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
                "save_path": t.get("save_path"),
                "root": root,
                "single_file": single_file,
                "size": t.get("total_size"),
                "added_on": t.get("added_on"),
            })
        return out


async def content_path(h: str) -> str:
    """qB's content_path for a torrent (qB's own filesystem view)."""
    async with client() as c:
        await login(c)
        fr = await c.get(_url("/api/v2/torrents/files"), params={"hash": h})
        if fr.status_code != 200:
            raise _fail(f"qB files failed: {fr.status_code}")
        if not fr.json():
            raise QbError("No files found for torrent", status=404)

        ir = await c.get(_url("/api/v2/torrents/info"), params={"hashes": h})
        info_list = ir.json() if ir.status_code == 200 else []
        info = info_list[0] if isinstance(info_list, list) and info_list else {}
        path = info.get("content_path") or ""
        if not path:
            raise QbError("Torrent content path not found", status=404)
        return path


async def set_category_best_effort(h: str, category: str):
    """Clear or change the category after import. Never fails the caller."""
    try:
        async with client(timeout=15) as c:
            await login(c)
            # Setting to empty string unsets the category on most qB versions.
            # If your qB requires an existing category, set QB_POSTIMPORT_CATEGORY_* to that name.
            await c.post(_url("/api/v2/torrents/setCategory"), data={"hashes": h, "category": category})
    except Exception:
        pass
