from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.observability.external import instrumented_httpx_request


@dataclass(frozen=True, slots=True)
class NominatimAddress:
    display_name: str | None
    street: str | None
    house_number: str | None
    postal_code: str | None
    city: str | None
    country: str | None


_cache: dict[tuple[float, float], tuple[float, NominatimAddress]] = {}


class NominatimService:
    async def reverse(self, latitude: float, longitude: float) -> NominatimAddress | None:
        settings = get_settings()
        if not settings.nominatim_base_url:
            return None

        key = (round(latitude, 5), round(longitude, 5))
        cached = _cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        params: dict[str, str | float | int] = {
            "lat": latitude,
            "lon": longitude,
            "format": "jsonv2",
            "addressdetails": 1,
            "zoom": 18,
        }
        if settings.nominatim_email:
            params["email"] = settings.nominatim_email

        endpoint = f"{settings.nominatim_base_url.rstrip('/')}/reverse"
        async with httpx.AsyncClient(
            timeout=settings.nominatim_timeout_seconds,
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            headers={"User-Agent": settings.nominatim_user_agent},
        ) as client:
            response = await instrumented_httpx_request(
                client, "GET", endpoint, provider="nominatim", operation="reverse", params=params
            )
            response.raise_for_status()
            payload = response.json()

        raw = payload.get("address") or {}
        address = NominatimAddress(
            display_name=payload.get("display_name"),
            street=raw.get("road") or raw.get("pedestrian") or raw.get("footway"),
            house_number=raw.get("house_number"),
            postal_code=raw.get("postcode"),
            city=raw.get("city") or raw.get("town") or raw.get("village") or raw.get("municipality"),
            country=raw.get("country"),
        )
        _cache[key] = (time.monotonic() + settings.nominatim_cache_ttl_seconds, address)
        return address
