import csv
import io
import re

from app.adapters.cube_sources.base import ImportedCube, ImportedCubeCard
from app.services.card_normalisation import parse_card_identifier


_COUNT_PREFIX_RE = re.compile(r"^\s*(?P<count>\d+)\s*[xX]?\s+(?P<name>.+?)\s*$")
_SET_NUMBER_RE = re.compile(
    r"^\s*(?P<name>.+?)\s*[,;]\s*(?P<set>[A-Za-z0-9]+)\s*[,;]\s*(?P<number>[A-Za-z0-9]+(?:/[A-Za-z0-9]+)?)\s*$"
)


def parse_manual_cube(name: str, text: str, author: str | None = None) -> ImportedCube:
    cards: dict[tuple[str, str | None, str | None], ImportedCubeCard] = {}
    stripped = text.strip()
    if not stripped:
        raise ValueError("Manual cube list is empty.")

    if "," in stripped.splitlines()[0]:
        parsed_cards = _parse_csv(stripped)
    else:
        parsed_cards = _parse_lines(stripped)

    for card in parsed_cards:
        key = (card.name, card.set_code, card.collector_number)
        if key in cards:
            existing = cards[key]
            cards[key] = ImportedCubeCard(
                name=existing.name,
                set_name=existing.set_name,
                set_code=existing.set_code,
                collector_number=existing.collector_number,
                quantity=existing.quantity + card.quantity,
                raw_source_data={"merged": [existing.raw_source_data, card.raw_source_data]},
            )
        else:
            cards[key] = card

    return ImportedCube(
        name=name.strip() or "Manual Cube",
        author=author.strip() if author else None,
        source_type="manual",
        cards=list(cards.values()),
        raw_source_data={"text": text},
    )


def _parse_lines(text: str) -> list[ImportedCubeCard]:
    cards = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = _COUNT_PREFIX_RE.match(line)
        quantity = int(match.group("count")) if match else 1
        name = match.group("name") if match else line
        set_code, collector_number = parse_card_identifier(name)
        structured = _SET_NUMBER_RE.match(name)
        if structured:
            name = structured.group("name")
            set_code = structured.group("set")
            collector_number = structured.group("number")
        cards.append(
            ImportedCubeCard(
                name=name.strip(),
                set_code=set_code,
                collector_number=collector_number,
                quantity=quantity,
                raw_source_data={"line": line},
            )
        )
    return cards


def _parse_csv(text: str) -> list[ImportedCubeCard]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV cube list has no headers.")
    headers = {header.casefold().strip(): header for header in reader.fieldnames}
    name_header = _first(headers, "name", "card name", "card", "card id", "card_id", "id")
    if not name_header:
        raise ValueError("CSV cube list needs a card name column.")
    cards = []
    for row in reader:
        quantity_header = _first(headers, "quantity", "qty", "count")
        quantity = int(row.get(quantity_header, "1") or "1") if quantity_header else 1
        parsed_set_code, parsed_number = parse_card_identifier(row[name_header])
        cards.append(
            ImportedCubeCard(
                name=row[name_header].strip(),
                set_name=_value(row, headers, "set", "set name"),
                set_code=_value(row, headers, "set code", "set_code") or parsed_set_code,
                collector_number=_value(row, headers, "collector number", "number")
                or parsed_number,
                quantity=quantity,
                raw_source_data=row,
            )
        )
    return cards


def _first(headers: dict[str, str], *names: str) -> str | None:
    for name in names:
        if name in headers:
            return headers[name]
    return None


def _value(row: dict[str, str], headers: dict[str, str], *names: str) -> str | None:
    header = _first(headers, *names)
    if not header:
        return None
    value = row.get(header, "").strip()
    return value or None
