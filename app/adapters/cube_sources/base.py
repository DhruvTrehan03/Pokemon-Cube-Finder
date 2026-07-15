from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ImportedCubeCard:
    name: str
    set_name: str | None = None
    set_code: str | None = None
    collector_number: str | None = None
    quantity: int = 1
    raw_source_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportedCube:
    name: str
    author: str | None = None
    description: str | None = None
    source_type: str = "manual"
    source_url: str | None = None
    cards: list[ImportedCubeCard] = field(default_factory=list)
    raw_source_data: dict[str, Any] = field(default_factory=dict)


class CubeSource(Protocol):
    async def fetch_cube(self, url: str) -> ImportedCube:
        ...
