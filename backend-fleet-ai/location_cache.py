"""
location_cache.py — All location data sourced from AWS RDS via the Orders API.

No hardcoded GPS coordinates anywhere in this file.
Delivery block and home pad coordinates are fetched at runtime and cached
in Redis for 60 seconds. Adding a new location row in the DB is instantly
picked up after the next cache expiry.

Public API:
    get_delivery_locations() -> List[dict]
    get_home_locations() -> List[dict]
    resolve_location_coords(name) -> tuple[float, float]
    prewarm_cache() -> None
"""
from __future__ import annotations

import json
import os
from typing import List

import httpx
import structlog

from redis_client import get_redis

log = structlog.get_logger(__name__)

ORDERS_API_BASE: str = os.getenv(
    "ORDERS_API_BASE",
    "https://fff8-2401-4900-cbd5-7c0d-d549-241c-a989-4b7a.ngrok-free.app",
)
CACHE_TTL_SECONDS: int = 60
_REDIS_KEY_DELIVERY = "location_cache:delivery"
_REDIS_KEY_HOME     = "location_cache:home"

# In-process fallback — populated after first successful API fetch
_last_known_delivery: List[dict] = []
_last_known_home:     List[dict] = []


async def _fetch_from_api(loc_type: str) -> List[dict]:
    """Fetch active locations of the given type from the Orders API."""
    url = f"{ORDERS_API_BASE}/api/locations"
    async with httpx.AsyncClient(
        timeout=10.0,
        headers={"ngrok-skip-browser-warning": "true"},
    ) as client:
        resp = await client.get(url, params={"type": loc_type})
        resp.raise_for_status()
    rows = resp.json()
    return [
        {
            "id":   r["id"],
            "name": r["name"],
            "lat":  float(r["latitude"]),
            "lon":  float(r["longitude"]),
        }
        for r in rows
        if r.get("is_active", True)
    ]


async def _get_cached_or_fetch(
    cache_key: str,
    loc_type: str,
    fallback: List[dict],
) -> List[dict]:
    """
    Try Redis cache first. On miss, fetch from Orders API and write cache.
    On API failure, return last known in-process data if available; otherwise raise.
    """
    # 1) Try Redis
    try:
        r = await get_redis()
        cached = await r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as cache_exc:
        log.warning(
            "location_cache_redis_read_error",
            event="location_cache_redis_read_error",
            service="fleet-ai",
            cache_key=cache_key,
            error=str(cache_exc),
        )

    # 2) Cache miss — fetch from API
    try:
        data = await _fetch_from_api(loc_type)
    except Exception as api_exc:
        log.warning(
            "location_cache_api_fetch_failed",
            event="location_cache_api_fetch_failed",
            service="fleet-ai",
            loc_type=loc_type,
            error=str(api_exc),
        )
        if fallback:
            log.warning(
                "location_cache_using_last_known",
                event="location_cache_using_last_known",
                service="fleet-ai",
                loc_type=loc_type,
                count=len(fallback),
            )
            return fallback
        raise RuntimeError(
            f"Cannot fetch location data for type '{loc_type}' and no fallback available: {api_exc}"
        ) from api_exc

    # 3) Write back to Redis
    try:
        r = await get_redis()
        await r.set(cache_key, json.dumps(data), ex=CACHE_TTL_SECONDS)
    except Exception as write_exc:
        log.warning(
            "location_cache_redis_write_error",
            event="location_cache_redis_write_error",
            service="fleet-ai",
            cache_key=cache_key,
            error=str(write_exc),
        )

    return data


async def get_delivery_locations() -> List[dict]:
    """Return all active DELIVERY_BLOCK locations from cache or RDS."""
    global _last_known_delivery
    result = await _get_cached_or_fetch(
        _REDIS_KEY_DELIVERY, "DELIVERY_BLOCK", _last_known_delivery
    )
    if result:
        _last_known_delivery = result
    return result


async def get_home_locations() -> List[dict]:
    """Return all active HOME pad locations from cache or RDS."""
    global _last_known_home
    result = await _get_cached_or_fetch(
        _REDIS_KEY_HOME, "HOME", _last_known_home
    )
    if result:
        _last_known_home = result
    return result


async def resolve_location_coords(name: str) -> tuple:
    """
    Case-insensitive name lookup across all location types.
    Supports underscore/space mapping and 'and'/'&' normalization.
    Returns (lat, lon). Raises KeyError if not found.
    """
    def normalize(val: str) -> str:
        return val.lower().replace("_", " ").replace("and", "&").replace("  ", " ").strip()

    name_norm = normalize(name)
    delivery_locs = await get_delivery_locations()
    home_locs     = await get_home_locations()
    for loc in delivery_locs + home_locs:
        if normalize(loc["name"]) == name_norm:
            return (loc["lat"], loc["lon"])
    raise KeyError(
        f"Location '{name}' not found in DELIVERY_BLOCK or HOME types. "
        f"Available: {[l['name'] for l in delivery_locs + home_locs]}"
    )


async def prewarm_cache() -> None:
    """Pre-warm Redis cache at startup — fail-safe (logs warning on error)."""
    try:
        delivery = await get_delivery_locations()
        home     = await get_home_locations()
        log.info(
            "location_cache_prewarmed",
            event="location_cache_prewarmed",
            service="fleet-ai",
            delivery_count=len(delivery),
            home_count=len(home),
        )
    except Exception as exc:
        log.warning(
            "location_cache_prewarm_failed",
            event="location_cache_prewarm_failed",
            service="fleet-ai",
            error=str(exc),
        )
