"""
MAM request cache utility for MAM Audiobook Finder.
Caches MAM search requests to reduce API calls (5 minute TTL).
"""
import time
import hashlib
import json
from typing import Optional, Dict, Any

# In-memory cache: {cache_key: (result, timestamp)}
_mam_cache: Dict[str, tuple[Any, float]] = {}

# Cache TTL in seconds (5 minutes)
MAM_CACHE_TTL = 300


def _get_cache_key(query: str, limit: int, sort_type: str = "default") -> str:
    """Generate cache key from search parameters."""
    cache_data = f"{query}|{limit}|{sort_type}"
    return hashlib.md5(cache_data.encode()).hexdigest()


def get_cached_mam_search(query: str, limit: int, sort_type: str = "default") -> Optional[Dict[str, Any]]:
    """
    Get cached MAM search result if available and not expired.

    Args:
        query: Search query text
        limit: Results limit
        sort_type: Sort type (default, seeders, added, etc.)

    Returns:
        Cached result dict if found and not expired, None otherwise
    """
    cache_key = _get_cache_key(query, limit, sort_type)

    if cache_key not in _mam_cache:
        return None

    result, timestamp = _mam_cache[cache_key]
    age = time.time() - timestamp

    if age > MAM_CACHE_TTL:
        # Expired - remove from cache
        del _mam_cache[cache_key]
        return None

    return result


def cache_mam_search(query: str, limit: int, result: Dict[str, Any], sort_type: str = "default") -> None:
    """
    Cache a MAM search result.

    Args:
        query: Search query text
        limit: Results limit
        result: Search result to cache
        sort_type: Sort type (default, seeders, added, etc.)
    """
    cache_key = _get_cache_key(query, limit, sort_type)
    _mam_cache[cache_key] = (result, time.time())


def clear_expired_cache() -> int:
    """
    Clear all expired cache entries.

    Returns:
        Number of entries cleared
    """
    now = time.time()
    to_delete = []

    for key, (_, timestamp) in _mam_cache.items():
        if now - timestamp > MAM_CACHE_TTL:
            to_delete.append(key)

    for key in to_delete:
        del _mam_cache[key]

    return len(to_delete)


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dict with cache_size, oldest_entry_age, newest_entry_age
    """
    if not _mam_cache:
        return {
            "cache_size": 0,
            "oldest_entry_age": 0,
            "newest_entry_age": 0
        }

    now = time.time()
    timestamps = [ts for _, ts in _mam_cache.values()]

    return {
        "cache_size": len(_mam_cache),
        "oldest_entry_age": int(now - min(timestamps)),
        "newest_entry_age": int(now - max(timestamps))
    }
