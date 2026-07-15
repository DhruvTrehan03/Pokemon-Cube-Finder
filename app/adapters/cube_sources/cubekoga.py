from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.adapters.cube_sources.base import ImportedCube, ImportedCubeCard
from app.config import get_settings
from app.services.card_normalisation import parse_card_identifier


class CubeKogaImportError(RuntimeError):
    pass


class CubeKogaSource:
    hostnames = {"cubekoga.net", "www.cubekoga.net"}
    api_base = "https://cubekoga.net/api"

    async def fetch_cube(self, url: str) -> ImportedCube:
        url = _normalise_url(url)
        parsed = urlparse(url)
        if parsed.netloc.casefold() not in self.hostnames:
            raise CubeKogaImportError("CubeKoga URLs must be on cubekoga.net.")

        slug = _extract_slug(parsed.path)
        if not slug:
            raise CubeKogaImportError("Could not identify a cube id or slug in that URL.")

        settings = get_settings()
        headers = {"User-Agent": settings.cubekoga_user_agent, "Accept": "application/json,text/html"}
        async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
            imported = await self._fetch_from_api(client, slug, url)
            if imported:
                return imported
            try:
                page = await client.get(url)
                page.raise_for_status()
            except httpx.HTTPError as exc:
                raise CubeKogaImportError(f"Could not fetch CubeKoga URL: {exc}") from exc

        embedded = _extract_embedded_json(page.text)
        if embedded:
            return _cube_from_json(embedded, url)
        raise CubeKogaImportError(
            "CubeKoga did not expose structured cube data this importer could read. "
            "Use manual cube import for this list, or paste a sample URL for adapter hardening."
        )

    async def _fetch_from_api(
        self, client: httpx.AsyncClient, slug: str, source_url: str
    ) -> ImportedCube | None:
        metadata = await _get_json(client, f"{self.api_base}/cubes/cube/{slug}")
        if metadata is None:
            metadata = await _get_json(client, f"{self.api_base}/cubes/shared/{slug}")
        if metadata is None and not slug.isdigit():
            metadata = await _search_cube_by_slug(client, self.api_base, slug)
        if not isinstance(metadata, dict):
            return None

        cube_id = metadata.get("cube_ID") or metadata.get("cubeId") or metadata.get("id")
        if not cube_id:
            return None
        cards_payload = await _get_json(client, f"{self.api_base}/cubes/{cube_id}/cards")
        if not isinstance(cards_payload, list):
            return None

        cards = [_card_from_json(card) for card in cards_payload if isinstance(card, dict)]
        cards = [card for card in cards if card.name]
        if not cards:
            return None
        return ImportedCube(
            name=str(metadata.get("cube_Name") or metadata.get("cubeName") or "CubeKoga Cube"),
            author=_string_or_none(metadata.get("creatorName")),
            description=_string_or_none(metadata.get("overview") or metadata.get("description")),
            source_type="cubekoga",
            source_url=source_url,
            cards=cards,
            raw_source_data={"metadata": metadata, "cards": cards_payload},
        )


def _normalise_url(url: str) -> str:
    url = url.strip()
    if not url:
        raise CubeKogaImportError("Enter a CubeKoga URL.")
    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        url = f"https://{url}"
    return url


def _extract_slug(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    for marker in ("cube", "cubes", "draft", "decks"):
        if marker in parts:
            index = parts.index(marker)
            if index + 1 < len(parts):
                return parts[index + 1]
    return parts[-1] if parts else None


def _candidate_json_urls(slug: str) -> list[str]:
    site = "https://cubekoga.net"
    api = "https://cubekoga.net/api"
    return [
        f"{api}/cubes/{slug}",
        f"{api}/cube/{slug}",
        f"{api}/public/cubes/{slug}",
        f"{api}/public/cube/{slug}",
        f"{api}/media/cube/{slug}/print-data",
        f"{api}/media/cube/{slug}/image-data",
        f"{site}/api/cubes/{slug}",
        f"{site}/api/cube/{slug}",
    ]


async def _get_json(client: httpx.AsyncClient, url: str) -> Any | None:
    try:
        response = await client.get(url)
    except httpx.HTTPError:
        return None
    if response.status_code == 404 or response.status_code >= 500:
        return None
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        return None
    try:
        return response.json()
    except ValueError:
        return None


async def _search_cube_by_slug(
    client: httpx.AsyncClient, api_base: str, slug: str
) -> dict[str, Any] | None:
    query = slug.replace("-", " ").replace("_", " ")
    payload = await _get_json(
        client,
        f"{api_base}/search/cubes?page=1&pageSize=10&sort=likes&q={quote(query)}&publicOnly=true",
    )
    if not isinstance(payload, dict):
        return None
    results = payload.get("results")
    if not isinstance(results, list):
        return None
    slug_key = re.sub(r"[^a-z0-9]", "", slug.casefold())
    for result in results:
        if not isinstance(result, dict):
            continue
        custom = str(result.get("cubeCustomUrl") or result.get("cube_Custom_URL") or "")
        name = str(result.get("cubeName") or result.get("cube_Name") or "")
        if slug_key in {
            re.sub(r"[^a-z0-9]", "", custom.casefold()),
            re.sub(r"[^a-z0-9]", "", name.casefold()),
        }:
            cube_id = result.get("cubeId") or result.get("cube_ID")
            if cube_id:
                return await _get_json(client, f"{api_base}/cubes/cube/{cube_id}")
    return None


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
        for key in ("cards", "cardList", "cubeCards", "mainboard", "printData"):
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
    name = str(
        source.get("name")
        or source.get("cardName")
        or source.get("card_Name")
        or source.get("card_ID")
        or source.get("cardId")
        or source.get("id")
        or ""
    ).strip()
    parsed_set_code, parsed_number = parse_card_identifier(name)
    return ImportedCubeCard(
        name=name,
        set_name=_string_or_none(source.get("setName") or source.get("set")),
        set_code=_string_or_none(
            source.get("setCode") or source.get("set_Code") or source.get("setId")
        )
        or parsed_set_code,
        collector_number=_string_or_none(
            source.get("collectorNumber")
            or source.get("set_Number")
            or source.get("number")
            or source.get("cardNumber")
        )
        or parsed_number,
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
