from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from app.settings import settings


class ArticNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class ArticArtwork:
    external_id: str
    title: str | None
    raw: dict


class _TTLCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, ArticArtwork]] = {}

    def get(self, key: str) -> ArticArtwork | None:
        item = self._data.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at < time.time():
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: ArticArtwork, ttl_seconds: int) -> None:
        self._data[key] = (time.time() + ttl_seconds, value)


_cache = _TTLCache()


async def fetch_artwork(external_id: str) -> ArticArtwork:
    cached = _cache.get(external_id)
    if cached:
        return cached

    url = f"{settings.artic_base_url}/artworks/{external_id}"
    timeout = httpx.Timeout(settings.artic_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url)

    if resp.status_code == 404:
        raise ArticNotFoundError(f"Artwork {external_id} not found")
    resp.raise_for_status()
    payload = resp.json()

    data = payload.get("data") or {}
    title = data.get("title")
    artwork = ArticArtwork(external_id=str(external_id), title=title, raw=payload)
    _cache.set(external_id, artwork, settings.artic_cache_ttl_seconds)
    return artwork

