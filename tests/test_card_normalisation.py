from app.services.card_normalisation import (
    clean_display_card_name,
    collector_number_and_total_match,
    collector_numbers_match,
    derive_set_code,
    normalise_card_name,
    normalise_collector_number,
    normalise_set_code,
    parse_card_identifier,
)


def test_normalise_card_name_preserves_mechanical_suffixes() -> None:
    assert normalise_card_name("  Mewtwo VSTAR  ") == "mewtwo vstar"
    assert normalise_card_name("Farfetch\u2019d") == "farfetch'd"
    assert normalise_card_name("Nidoran\u2640") == "nidoran\u2640"


def test_normalise_set_code_and_collector_number() -> None:
    assert normalise_set_code(" sv1 ") == "SV1"
    assert normalise_collector_number(" # 012 / 198 ") == "012/198"


def test_derives_tcgplayer_set_prefix_and_cleans_name_suffixes() -> None:
    assert derive_set_code("SWSH11: Lost Origin") == "SWSH11"
    assert clean_display_card_name("Jacinthe - 075/088") == "Jacinthe"
    assert normalise_card_name("Clefairy - 030/088") == "clefairy"


def test_parses_cubekoga_card_identifier() -> None:
    assert parse_card_identifier("swsh11-046") == ("SWSH11", "046")
    assert parse_card_identifier("ex6-112") == ("EX6", "112")
    assert collector_numbers_match("046/196", "046")
    assert collector_number_and_total_match("046/196", "046", "196")
    assert not collector_number_and_total_match("046/196", "046", "200")
