from app.services.collection_import import detect_columns, parse_collection_csv, sniff_csv


def test_detects_likely_tcgplayer_columns() -> None:
    headers, _rows = sniff_csv("Product Name,Set Name,Number,Quantity\nPikachu,Base,58,2\n")

    detection = detect_columns(headers)

    assert detection.mapping["name"] == "Product Name"
    assert detection.mapping["set_name"] == "Set Name"
    assert detection.mapping["collector_number"] == "Number"
    assert detection.mapping["quantity"] == "Quantity"
    assert detection.missing_required == []


def test_csv_import_merges_duplicate_rows() -> None:
    raw = (
        "Product Name,Set Code,Number,Quantity,Condition\n"
        "Pikachu,BS,58,1,NM\n"
        "Pikachu,BS,58,2,NM\n"
    )
    headers, _rows = sniff_csv(raw)
    mapping = detect_columns(headers).mapping

    cards = parse_collection_csv(raw, mapping)

    assert len(cards) == 1
    assert cards[0].quantity == 3
    assert cards[0].set_code == "BS"
    assert cards[0].collector_number == "58"


def test_csv_import_derives_set_code_from_tcgplayer_set_name() -> None:
    raw = "Product Name,Set Name,Number,Quantity\nDucklett,SWSH11: Lost Origin,046/196,1\n"
    headers, _rows = sniff_csv(raw)
    mapping = detect_columns(headers).mapping

    cards = parse_collection_csv(raw, mapping)

    assert cards[0].original_name == "Ducklett"
    assert cards[0].set_code == "SWSH11"
    assert cards[0].collector_number == "046/196"
