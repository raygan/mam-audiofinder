"""
Search routes for MAM Audiobook Finder.
"""
import json
import re
import asyncio
import logging
import random
import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from config import MAM_BASE, MAM_COOKIE, ABS_BASE_URL, ABS_API_KEY, ABS_CHECK_LIBRARY
from abs_client import abs_client
from mam_cache import get_cached_mam_search, cache_mam_search

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
    """Search MAM for audiobooks with 5-minute caching."""
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
    query_text = tor.get("text", "")
    sort_type = tor.get("sortType", "default")

    # Check cache first
    cached = get_cached_mam_search(query_text, perpage, sort_type)
    if cached:
        logger.info(f"✅ Cache HIT for query='{query_text}', limit={perpage}")
        return cached

    logger.info(f"❌ Cache MISS for query='{query_text}', limit={perpage} - fetching from MAM")
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
            "in_abs_library": False,  # Default to False, will be updated below
        })

    # Check which items exist in ABS library (if feature enabled)
    if ABS_CHECK_LIBRARY and out:
        try:
            # Extract (title, author) pairs from results
            items_to_check = [(result["title"] or "", result["author_info"] or "") for result in out]

            # Call library check
            library_results = await abs_client.check_library_items(items_to_check)

            # Update results with library status
            for result in out:
                cache_key = f"{(result['title'] or '').lower().strip()}||{(result['author_info'] or '').lower().strip()}"
                result["in_abs_library"] = library_results.get(cache_key, False)

            logger.info(f"📚 Library check: {sum(r['in_abs_library'] for r in out)}/{len(out)} items found in ABS")
        except Exception as e:
            logger.error(f"❌ Library check failed: {e}")
            # Continue with in_abs_library=False on error

    # NOTE: We no longer fetch covers during search to avoid blocking.
    # Covers are fetched progressively via the /api/covers/fetch endpoint.
    logger.info(f"✅ Returning {len(out)} search results (covers will load progressively)")

    response_data = {
        "results": out,
        "total": raw.get("total"),
        "total_found": raw.get("total_found"),
    }

    # Cache the result for 5 minutes
    cache_mam_search(query_text, perpage, response_data, sort_type)

    return JSONResponse(response_data)


@router.get("/api/covers/fetch")
async def fetch_cover(
    mam_id: str = Query(..., description="MAM torrent ID"),
    title: str = Query("", description="Book title"),
    author: str = Query("", description="Book author"),
    max_retries: int = Query(2, description="Maximum number of retries")
):
    """
    Fetch cover for a specific MAM ID with retry logic.
    Returns immediately with cover URL or error.
    """
    if not ABS_BASE_URL or not ABS_API_KEY:
        return JSONResponse({
            "mam_id": mam_id,
            "cover_url": None,
            "item_id": None,
            "error": "ABS not configured"
        })

    if not title:
        return JSONResponse({
            "mam_id": mam_id,
            "cover_url": None,
            "item_id": None,
            "error": "No title provided"
        })

    # Retry logic with exponential backoff and jitter
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                # Exponential backoff with jitter: base delay * 2^(attempt-1) + random jitter
                base_delay = 0.5 * (2 ** (attempt - 1))
                jitter = random.random() * (base_delay * 0.5)
                wait_time = base_delay + jitter
                logger.info(f"🔄 Retry {attempt}/{max_retries} for '{title}' after {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)

            result = await abs_client.fetch_cover(title, author, mam_id)

            if result and result.get("cover_url"):
                logger.info(f"✅ Cover fetch succeeded for '{title}' on attempt {attempt + 1}")
                response = {
                    "mam_id": mam_id,
                    "cover_url": result.get("cover_url"),
                    "item_id": result.get("item_id"),
                    "error": None
                }
                # Include description and metadata if available
                if result.get("description"):
                    response["description"] = result.get("description")
                if result.get("metadata"):
                    response["metadata"] = result.get("metadata")
                return JSONResponse(response)
            else:
                # No cover found, but not an error - don't retry
                logger.info(f"ℹ️  No cover found for '{title}'")
                return JSONResponse({
                    "mam_id": mam_id,
                    "cover_url": None,
                    "item_id": None,
                    "error": "No cover found"
                })

        except httpx.ReadTimeout as e:
            last_error = f"Timeout: {e}"
            logger.warning(f"⏱️  Timeout fetching cover for '{title}' (attempt {attempt + 1}/{max_retries + 1})")
            continue
        except httpx.ConnectTimeout as e:
            last_error = f"Connection timeout: {e}"
            logger.warning(f"⏱️  Connection timeout for '{title}' (attempt {attempt + 1}/{max_retries + 1})")
            continue
        except httpx.HTTPError as e:
            last_error = f"HTTP error: {e}"
            logger.warning(f"❌ HTTP error fetching cover for '{title}': {e}")
            continue
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            logger.error(f"❌ Unexpected error fetching cover for '{title}': {e}")
            continue

    # All retries exhausted
    logger.error(f"❌ All {max_retries + 1} attempts failed for '{title}': {last_error}")
    return JSONResponse({
        "mam_id": mam_id,
        "cover_url": None,
        "item_id": None,
        "error": last_error
    })
