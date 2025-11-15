"""
Search routes for MAM Audiobook Finder.
"""
import json
import re
import asyncio
import logging
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from config import MAM_BASE, MAM_COOKIE, ABS_BASE_URL, ABS_API_KEY
from abs_client import abs_client

router = APIRouter()
logger = logging.getLogger("mam-audiofinder")


def flatten(v):
    """Normalize MAM API response data (handles dicts, lists, JSON strings)."""
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
    """Extract file format from torrent metadata."""
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


@router.post("/search")
async def search(payload: dict):
    """Search MAM for audiobooks."""
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

    # Fetch covers from Audiobookshelf (if configured)
    if ABS_BASE_URL and ABS_API_KEY and out:
        logger.info(f"📚 Fetching covers for {len(out)} search results...")
        # Fetch covers in parallel for all results
        cover_tasks = []
        for result in out:
            title = result.get("title") or ""
            author = result.get("author_info") or ""
            mam_id = result.get("id") or ""
            cover_tasks.append(abs_client.fetch_cover(title, author, mam_id))

        cover_results = await asyncio.gather(*cover_tasks, return_exceptions=True)

        # Add cover URLs to results
        covers_added = 0
        for i, cover_data in enumerate(cover_results):
            if isinstance(cover_data, dict) and cover_data:
                out[i]["abs_cover_url"] = cover_data.get("cover_url")
                out[i]["abs_item_id"] = cover_data.get("item_id")
                if cover_data.get("cover_url"):
                    covers_added += 1
            elif isinstance(cover_data, Exception):
                logger.error(f"❌ Cover fetch exception for result {i}: {cover_data}")

        logger.info(f"✅ Added {covers_added} cover URLs to search results")
    else:
        if not ABS_BASE_URL or not ABS_API_KEY:
            logger.info(f"ℹ️  Skipping cover fetch: ABS not configured (URL={bool(ABS_BASE_URL)}, KEY={bool(ABS_API_KEY)})")
        elif not out:
            logger.info(f"ℹ️  Skipping cover fetch: no search results")

    return JSONResponse({
        "results": out,
        "total": raw.get("total"),
        "total_found": raw.get("total_found"),
    })
