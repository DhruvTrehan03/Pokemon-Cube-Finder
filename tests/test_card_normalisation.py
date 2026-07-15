from app.services.card_normalisation import (
    normalise_card_name,
    normalise_collector_number,
    normalise_set_code,
)


def test_normalise_card_name_preserves_mechanical_suffixes() -> None:
    assert normalise_card_name("  Mewtwo VSTAR  ") == "mewtwo vstar"
    assert normalise_card_name("Farfetch\u2019d") == "farfetch'd"
    assert normalise_card_name("Nidoran\u2640") == "nidoran\u2640"


def test_normalise_set_code_and_collector_number() -> None:
    assert normalise_set_code(" sv1 ") == "SV1"
    assert normalise_collector_number(" # 012 / 198 ") == "012/198"
