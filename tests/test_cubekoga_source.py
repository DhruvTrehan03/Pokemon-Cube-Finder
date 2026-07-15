from app.adapters.cube_sources.cubekoga import _card_from_json, _normalise_url


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
