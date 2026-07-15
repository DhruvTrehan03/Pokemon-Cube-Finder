import csv
import io
import json
from dataclasses import dataclass
from typing import Any

from app.services.card_normalisation import (
    clean_display_card_name,
    derive_set_code,
    normalise_card_name,
    normalise_collector_number,
    normalise_set_code,
    normalise_set_name,
)


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("product name", "card name", "name", "title", "card"),
    "set_name": ("set name", "set", "expansion", "series"),
    "set_code": ("set code", "set abbreviation", "set id", "expansion code"),
    "collector_number": (
        "collector number",
        "card number",
        "number",
        "collector no",
        "coll no",
    ),
    "quantity": ("quantity", "qty", "count", "total quantity", "owned quantity"),
    "printing": ("printing", "variant", "finish", "foil", "language"),
    "condition": ("condition", "card condition"),
}


REQUIRED_FIELDS = ("name", "quantity")


@dataclass(frozen=True)
class ColumnDetection:
    headers: list[str]
    mapping: dict[str, str | None]
    missing_required: list[str]


@dataclass(frozen=True)
class ParsedOwnedCard:
    original_name: str
    normalised_name: str
    set_name: str | None
    normalised_set_name: str | None
    set_code: str | None
    collector_number: str | None
    quantity: int
    printing: str | None
    condition: str | None
    raw_import_data: dict[str, Any]


def sniff_csv(raw_csv: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(raw_csv))
    headers = list(reader.fieldnames or [])
    rows = [dict(row) for row in reader]
    return headers, rows


def detect_columns(headers: list[str]) -> ColumnDetection:
    normalised_headers = {header.strip().casefold(): header for header in headers}
    mapping: dict[str, str | None] = {}
    for field, aliases in FIELD_ALIASES.items():
        found = None
        for alias in aliases:
            if alias in normalised_headers:
                found = normalised_headers[alias]
                break
        if found is None:
            for candidate_key, candidate_header in normalised_headers.items():
                if any(alias in candidate_key for alias in aliases):
                    found = candidate_header
                    break
        mapping[field] = found
    missing_required = [field for field in REQUIRED_FIELDS if not mapping.get(field)]
    return ColumnDetection(headers=headers, mapping=mapping, missing_required=missing_required)


def parse_quantity(value: str | None) -> int:
    if value is None or not str(value).strip():
        return 1
    try:
        parsed = int(float(str(value).strip()))
    except ValueError as exc:
        raise ValueError(f"Invalid quantity: {value}") from exc
    if parsed < 0:
        raise ValueError(f"Quantity cannot be negative: {value}")
    return parsed


def parse_collection_csv(raw_csv: str, mapping: dict[str, str | None]) -> list[ParsedOwnedCard]:
    _headers, rows = sniff_csv(raw_csv)
    cards: dict[tuple[str, str | None, str | None, str | None, str | None], ParsedOwnedCard] = {}
    for row in rows:
        name_header = mapping.get("name")
        if not name_header or not row.get(name_header, "").strip():
            continue
        set_name = _optional(row, mapping.get("set_name"))
        set_code = normalise_set_code(_optional(row, mapping.get("set_code"))) or derive_set_code(
            set_name
        )
        collector_number = normalise_collector_number(
            _optional(row, mapping.get("collector_number"))
        )
        printing = _optional(row, mapping.get("printing"))
        condition = _optional(row, mapping.get("condition"))
        parsed = ParsedOwnedCard(
            original_name=clean_display_card_name(row[name_header]),
            normalised_name=normalise_card_name(row[name_header]),
            set_name=set_name,
            normalised_set_name=normalise_set_name(set_name),
            set_code=set_code,
            collector_number=collector_number,
            quantity=parse_quantity(_optional(row, mapping.get("quantity"))),
            printing=printing,
            condition=condition,
            raw_import_data=row,
        )
        key = (
            parsed.normalised_name,
            parsed.set_code,
            parsed.collector_number,
            parsed.printing,
            parsed.condition,
        )
        if key in cards:
            existing = cards[key]
            cards[key] = ParsedOwnedCard(
                **{
                    **existing.__dict__,
                    "quantity": existing.quantity + parsed.quantity,
                    "raw_import_data": {
                        "merged_rows": [
                            json.loads(json.dumps(existing.raw_import_data)),
                            row,
                        ]
                    },
                }
            )
        else:
            cards[key] = parsed
    return list(cards.values())


def _optional(row: dict[str, str], header: str | None) -> str | None:
    if not header:
        return None
    value = row.get(header)
    if value is None:
        return None
    value = value.strip()
    return value or None
