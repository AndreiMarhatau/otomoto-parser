from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


_GEOCODE_CACHE: dict[str, dict[str, Any] | None] = {}


def geocode_location(query: str) -> dict[str, Any] | None:
    cached = _GEOCODE_CACHE.get(query)
    if cached is not None or query in _GEOCODE_CACHE:
        return cached
    request = Request(
        f"https://nominatim.openstreetmap.org/search?{urlencode({'format': 'jsonv2', 'limit': 1, 'q': query})}",
        headers={"User-Agent": "otomoto-parser/0.1.0", "Accept-Language": "en"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError("Could not load map preview.") from exc
    if not payload:
        _GEOCODE_CACHE[query] = None
        return None
    first = payload[0]
    result = {"lat": float(first["lat"]), "lon": float(first["lon"]), "label": first.get("display_name") or query}
    _GEOCODE_CACHE[query] = result
    return result
