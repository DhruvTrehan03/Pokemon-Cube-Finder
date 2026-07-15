from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.adapters.cube_sources.base import ImportedCube, ImportedCubeCard
from app.config import get_settings


class CubeKogaImportError(RuntimeError):
    pass


class CubeKogaSource:
    hostnames = {"cubekoga.net", "www.cubekoga.net"}

    async def fetch_cube(self, url: str) -> ImportedCube:
        parsed = urlparse(url)
        if parsed.netloc.casefold() not in self.hostnames:
            raise CubeKogaImportError("CubeKoga URLs must be on cubekoga.net.")

        slug = _extract_slug(parsed.path)
        if not slug:
            raise CubeKogaImportError("Could not identify a cube id or slug in that URL.")

        settings = get_settings()
        headers = {"User-Agent": settings.cubekoga_user_agent, "Accept": "application/json,text/html"}
        async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
            for endpoint in _candidate_json_urls(slug):
                response = await client.get(endpoint)
                if response.status_code == 404:
                    continue
                if response.headers.get("content-type", "").startswith("application/json"):
                    return _cube_from_json(response.json(), url)
            page = await client.get(url)
            page.raise_for_status()

        embedded = _extract_embedded_json(page.text)
        if embedded:
            return _cube_from_json(embedded, url)
        raise CubeKogaImportError(
            "CubeKoga did not expose structured cube data this importer could read. "
            "Use manual cube import for this list, or paste a sample URL for adapter hardening."
        )


def _extract_slug(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    for marker in ("cube", "cubes", "draft", "decks"):
        if marker in parts:
            index = parts.index(marker)
            if index + 1 < len(parts):
                return parts[index + 1]
    return parts[-1] if parts else None


def _candidate_json_urls(slug: str) -> list[str]:
    base = "https://cubekoga.net"
    return [
        f"{base}/api/cubes/{slug}",
        f"{base}/api/cube/{slug}",
        f"{base}/api/public/cubes/{slug}",
        f"{base}/api/public/cube/{slug}",
    ]


def _extract_embedded_json(html: str) -> dict[str, Any] | None:
    # Angular currently serves an empty app shell, but this keeps the adapter ready
    # if CubeKoga later embeds transfer state or JSON-LD data.
    for pattern in (
        r'<script[^>]+type="application/json"[^>]*>(?P<json>.*?)</script>',
        r'<script[^>]+type="application/ld\+json"[^>]*>(?P<json>.*?)</script>',
    ):
        match = re.search(pattern, html, flags=re.DOTALL | re.IGNORECASE)
        if not match:
            continue
        try:
            import json

            return json.loads(match.group("json"))
        except ValueError:
            continue
    return None


def _cube_from_json(payload: dict[str, Any], source_url: str) -> ImportedCube:
    cube_data = _find_cube_object(payload) or payload
    cards_data = _find_cards(cube_data)
    cards = [_card_from_json(card) for card in cards_data]
    cards = [card for card in cards if card.name]
    if not cards:
        raise CubeKogaImportError("CubeKoga response did not contain readable card entries.")
    return ImportedCube(
        name=str(cube_data.get("name") or cube_data.get("title") or "CubeKoga Cube"),
        author=_string_or_none(cube_data.get("author") or cube_data.get("ownerName")),
        description=_string_or_none(cube_data.get("description")),
        source_type="cubekoga",
        source_url=source_url,
        cards=cards,
        raw_source_data=payload,
    )


def _find_cube_object(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        if any(key in payload for key in ("cards", "cardList", "cubeCards")):
            return payload
        for key in ("cube", "data", "result"):
            found = _find_cube_object(payload.get(key))
            if found:
                return found
    return None


def _find_cards(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("cards", "cardList", "cubeCards", "mainboard"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        for value in payload.values():
            found = _find_cards(value)
            if found:
                return found
    return []


def _card_from_json(card: dict[str, Any]) -> ImportedCubeCard:
    nested = card.get("card") if isinstance(card.get("card"), dict) else {}
    source = {**nested, **card}
    return ImportedCubeCard(
        name=str(source.get("name") or source.get("cardName") or "").strip(),
        set_name=_string_or_none(source.get("setName") or source.get("set")),
        set_code=_string_or_none(source.get("setCode") or source.get("setId")),
        collector_number=_string_or_none(
            source.get("collectorNumber") or source.get("number") or source.get("cardNumber")
        ),
        quantity=_int_or_one(source.get("quantity") or source.get("count") or source.get("qty")),
        raw_source_data=card,
    )


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_one(value: Any) -> int:
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return 1
