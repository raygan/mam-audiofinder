"""
qBittorrent routes for MAM Audiobook Finder.
"""
import logging
import httpx
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from config import (
    MAM_BASE, MAM_COOKIE, QB_URL, QB_CATEGORY, QB_TAGS, QB_SAVEPATH
)
from db import engine
from qb_client import qb_login
from torrent_helpers import extract_mam_id_from_tags

router = APIRouter()
logger = logging.getLogger("mam-audiofinder")


class AddBody(BaseModel):
    """Request body for adding torrent to qBittorrent."""
    id: str | int | None = None
    title: str | None = None
    dl: str | None = None
    author: str | None = None
    narrator: str | None = None
    abs_cover_url: str | None = None
    abs_item_id: str | None = None


@router.get("/qb/torrents")
async def qb_torrents():
    """List completed torrents from qBittorrent."""
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

            # Extract MAM ID from tags
            tags = t.get("tags", "")
            mam_id = extract_mam_id_from_tags(tags)

            # Get content_path for better matching
            content_path = t.get("content_path", "")

            out.append({
                "hash": h,
                "name": t.get("name"),
                "save_path": t.get("save_path"),  # absolute host path, but we mounted /media so it should start with /media
                "content_path": content_path,
                "root": root,
                "single_file": single_file,
                "size": t.get("total_size"),
                "added_on": t.get("added_on"),
                "mam_id": mam_id,  # NEW: extracted from tags
            })
        return {"items": out}


@router.post("/add")
async def add_to_qb(body: AddBody):
    """Add torrent to qBittorrent."""
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
