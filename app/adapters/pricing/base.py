from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class CardPriceQuery:
    name: str
    set_code: str | None
    collector_number: str | None


@dataclass(frozen=True)
class CardPrice:
    query: CardPriceQuery
    amount: Decimal
    currency: str
    source: str


class PriceProvider(Protocol):
    async def get_prices(
        self,
        cards: list[CardPriceQuery],
    ) -> dict[CardPriceQuery, CardPrice | None]:
        ...
