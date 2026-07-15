import pytest

import app.adapters.cube_sources.cubekoga as cubekoga
from app.adapters.cube_sources.cubekoga import CubeKogaSource, _card_from_json, _normalise_url


def test_cubekoga_url_accepts_missing_scheme() -> None:
    assert _normalise_url("cubekoga.net/cube/abc") == "https://cubekoga.net/cube/abc"


def test_cubekoga_json_card_id_becomes_identifier_match_data() -> None:
    card = _card_from_json({"card_ID": "swsh11-046", "quantity": 2})

    assert card.name == "swsh11-046"
    assert card.set_code == "SWSH11"
    assert card.collector_number == "046"
    assert card.quantity == 2


def test_cubekoga_real_card_fields_are_read() -> None:
    card = _card_from_json(
        {"card_ID": "dp3-20", "card_Name": "Venusaur", "set_Code": "dp3", "set_Number": "20"}
    )

    assert card.name == "Venusaur"
    assert card.set_code == "dp3"
    assert card.collector_number == "20"


@pytest.mark.asyncio
async def test_iter_public_cubes_reads_cubekoga_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_json(_client: object, url: str) -> object:
        if "/cubes/all" in url:
            return {
                "items": [
                    {
                        "cube_ID": 123,
                        "cube_Name": "Starter Cube",
                        "creatorName": "Ash",
                    }
                ],
                "hasMore": False,
                "totalCount": 1,
            }
        if url.endswith("/cubes/123/cards"):
            return [
                {
                    "card_ID": "base1-4",
                    "card_Name": "Charizard",
                    "set_Code": "base1",
                    "set_Number": "4",
                }
            ]
        return None

    monkeypatch.setattr(cubekoga, "_get_json", fake_get_json)

    cubes = [
        cube
        async for cube in CubeKogaSource().iter_public_cubes(
            page_size=50, delay_seconds=0, max_cubes=1
        )
    ]

    assert len(cubes) == 1
    assert cubes[0].name == "Starter Cube"
    assert cubes[0].author == "Ash"
    assert cubes[0].source_url == "https://cubekoga.net/cube/123"
    assert cubes[0].cards[0].name == "Charizard"
