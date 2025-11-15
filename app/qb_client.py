"""
qBittorrent API client for MAM Audiobook Finder.
"""
import httpx
from fastapi import HTTPException

from config import QB_URL, QB_USER, QB_PASS


async def qb_login(client: httpx.AsyncClient):
    """Login to qBittorrent WebUI."""
    r = await client.post(f"{QB_URL}/api/v2/auth/login",
                          data={"username": QB_USER, "password": QB_PASS},
                          timeout=20)
    if r.status_code != 200 or "Ok" not in (r.text or ""):
        raise HTTPException(status_code=502, detail=f"qB login failed: {r.status_code} {r.text[:120]}")


def qb_login_sync(client: httpx.Client):
    """Synchronous login to qBittorrent WebUI."""
    r = client.post(f"{QB_URL}/api/v2/auth/login",
                   data={"username": QB_USER, "password": QB_PASS})
    if r.status_code != 200 or "Ok" not in r.text:
        raise HTTPException(status_code=502, detail="qB login failed")
