"""
Showcase routes for MAM Audiobook Finder.
Displays audiobooks in a grouped grid view similar to Audible.
"""
import json
import re
import logging
import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from collections import defaultdict
from typing import Dict, List

from config import MAM_BASE, MAM_COOKIE
from abs_client import abs_client

router = APIRouter()
logger = logging.getLogger("mam-audiofinder")


def normalize_title(title: str) -> str:
    """
    Normalize a title for grouping purposes.
    Removes articles (The, A, An), punctuation, and extra whitespace.
    Converts to lowercase for case-insensitive matching.
    """
    if not title:
        return ""

    # Remove common articles at the start
    s = re.sub(r'^(The|A|An)\s+', '', title, flags=re.IGNORECASE)

    # Remove punctuation and special characters
    s = re.sub(r'[^\w\s]', '', s)

    # Normalize whitespace
    s = re.sub(r'\s+', ' ', s).strip()

    # Convert to lowercase
    return s.lower()


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


@router.get("/showcase")
async def showcase(
    query: str = Query("", description="Search query (optional, defaults to recent audiobooks)"),
    limit: int = Query(100, description="Maximum number of results to fetch", ge=1, le=500)
):
    """
    Search MAM and return results grouped by normalized title for showcase grid view.

    Returns:
        - groups: List of title groups, each containing:
            - normalized_title: The normalized title used for grouping
            - display_title: The most common/best title to display
            - author: The most common author
            - narrator: The most common narrator (if available)
            - formats: List of unique formats available
            - versions: List of all torrents in this group
            - cover_url: Cover URL (fetched from ABS if available)
            - total_versions: Count of versions
    """
    if not MAM_COOKIE:
        raise HTTPException(status_code=500, detail="MAM_COOKIE not set on server")

    # Build MAM search payload
    tor = {
        "text": query,
        "srchIn": ["title", "author", "narrator"],
        "searchType": "all",
        "sortType": "default",
        "startNumber": "0",
        "main_cat": ["13"],  # Audiobooks
    }

    body = {"tor": tor, "perpage": limit}

    headers = {
        "Cookie": MAM_COOKIE,
        "Content-Type": "application/json",
        "Accept": "application/json, */*",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://www.myanonamouse.net",
        "Referer": "https://www.myanonamouse.net/",
    }
    params = {"dlLink": "1"}

    # Fetch from MAM
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

    # Parse and group results
    groups_dict: Dict[str, List[dict]] = defaultdict(list)

    for item in raw.get("data", []):
        title = item.get("title") or item.get("name") or "Unknown"
        normalized = normalize_title(title)

        # Skip empty titles
        if not normalized:
            continue

        parsed_item = {
            "id": str(item.get("id") or item.get("tid") or ""),
            "title": title,
            "author_info": flatten(item.get("author_info")),
            "narrator_info": flatten(item.get("narrator_info")),
            "format": detect_format(item),
            "size": item.get("size"),
            "seeders": item.get("seeders"),
            "leechers": item.get("leechers"),
            "catname": item.get("catname"),
            "added": item.get("added"),
            "dl": item.get("dl"),
        }

        groups_dict[normalized].append(parsed_item)

    # Convert to list of group objects
    groups = []
    for normalized_title, versions in groups_dict.items():
        # Pick the most representative title (shortest non-empty one)
        display_title = min(
            (v["title"] for v in versions if v["title"]),
            key=len,
            default="Unknown"
        )

        # Pick the most common author
        authors = [v["author_info"] for v in versions if v["author_info"]]
        author = max(set(authors), key=authors.count) if authors else ""

        # Pick the most common narrator
        narrators = [v["narrator_info"] for v in versions if v["narrator_info"]]
        narrator = max(set(narrators), key=narrators.count) if narrators else ""

        # Collect unique formats
        formats = list(set(v["format"] for v in versions if v["format"]))

        # Sort versions by seeders (descending) for best match first
        versions.sort(key=lambda x: int(x.get("seeders") or 0), reverse=True)

        groups.append({
            "normalized_title": normalized_title,
            "display_title": display_title,
            "author": author,
            "narrator": narrator,
            "formats": formats,
            "versions": versions,
            "total_versions": len(versions),
            # Cover will be fetched progressively on the frontend
            "cover_url": None,
            # Use the first version's ID for cover lookup
            "mam_id": versions[0]["id"] if versions else None,
        })

    # Sort groups by total versions (descending) to show popular titles first
    groups.sort(key=lambda x: x["total_versions"], reverse=True)

    logger.info(f"✅ Showcase: Returning {len(groups)} title groups from {len(raw.get('data', []))} results")

    return JSONResponse({
        "groups": groups,
        "total_groups": len(groups),
        "total_results": len(raw.get("data", [])),
        "query": query,
    })
