from app.adapters.cube_sources.manual import parse_manual_cube


def test_manual_cube_line_import() -> None:
    cube = parse_manual_cube("Starter Cube", "2 Pikachu\nCharmander\n")

    assert cube.name == "Starter Cube"
    assert len(cube.cards) == 2
    assert cube.cards[0].quantity == 2
    assert cube.cards[1].name == "Charmander"


def test_manual_cube_parses_cubekoga_card_ids() -> None:
    cube = parse_manual_cube("CubeKoga IDs", "swsh11-046\n2 ex6-112\n")

    assert cube.cards[0].name == "swsh11-046"
    assert cube.cards[0].set_code == "SWSH11"
    assert cube.cards[0].collector_number == "046"
    assert cube.cards[1].quantity == 2
    assert cube.cards[1].set_code == "EX6"


def test_manual_cube_csv_import() -> None:
    cube = parse_manual_cube(
        "CSV Cube",
        "Name,Set Code,Collector Number,Quantity\nPikachu,BS,58,2\n",
    )

    assert cube.cards[0].name == "Pikachu"
    assert cube.cards[0].set_code == "BS"
    assert cube.cards[0].collector_number == "58"
    assert cube.cards[0].quantity == 2
