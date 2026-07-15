from dataclasses import dataclass, field
from enum import StrEnum

from app.services.card_normalisation import (
    card_signature,
    collector_number_and_total_match,
    collector_numbers_match,
)


class MatchStatus(StrEnum):
    EXACT = "exact"
    SET_NUMBER = "set_number"
    NAME_ONLY = "name_only"
    UNRESOLVED = "unresolved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class OwnedCardInput:
    id: int
    original_name: str
    normalised_name: str
    set_code: str | None
    collector_number: str | None
    quantity: int


@dataclass(frozen=True)
class CubeCardInput:
    id: int
    original_name: str
    normalised_name: str
    set_name: str | None
    set_code: str | None
    collector_number: str | None
    required_quantity: int
    set_total: str | None = None
    tcgplayer_market_price: float | None = None
    cardmarket_market_price: float | None = None


@dataclass(frozen=True)
class OwnedAllocation:
    owned_card_id: int
    original_name: str
    quantity: int
    status: MatchStatus


@dataclass
class CubeCardAllocation:
    cube_card: CubeCardInput
    owned_quantity: int = 0
    missing_quantity: int = 0
    status: MatchStatus = MatchStatus.UNRESOLVED
    allocations: list[OwnedAllocation] = field(default_factory=list)


def allocate_cards(
    owned_cards: list[OwnedCardInput],
    cube_cards: list[CubeCardInput],
    rejected_pairs: set[tuple[str, str]] | None = None,
) -> list[CubeCardAllocation]:
    rejected_pairs = rejected_pairs or set()
    sorted_owned = sorted(owned_cards, key=lambda card: (card.original_name, card.id))
    exact_index: dict[str, list[OwnedCardInput]] = {}
    name_index: dict[str, list[OwnedCardInput]] = {}
    for owned in sorted_owned:
        if owned.set_code and owned.collector_number:
            exact_index.setdefault(owned.set_code, []).append(owned)
        if owned.normalised_name:
            name_index.setdefault(owned.normalised_name, []).append(owned)

    remaining = {card.id: max(card.quantity, 0) for card in sorted_owned}
    results: list[CubeCardAllocation] = []

    for cube_card in sorted(cube_cards, key=lambda card: (card.normalised_name, card.id)):
        required = max(cube_card.required_quantity, 0)
        result = CubeCardAllocation(
            cube_card=cube_card,
            missing_quantity=required,
        )

        exact_pool = []
        if cube_card.set_code and cube_card.collector_number:
            exact_pool = exact_index.get(cube_card.set_code, [])
        exact_candidates = _available_candidates(
            exact_pool,
            cube_card,
            remaining,
            rejected_pairs,
            require_name=not _looks_identifier_only(cube_card.original_name),
            require_number_match=True,
        )
        _consume(result, exact_candidates, remaining, required, MatchStatus.EXACT)

        if result.owned_quantity < required:
            set_number_candidates = _available_candidates(
                name_index.get(cube_card.normalised_name, []),
                cube_card,
                remaining,
                rejected_pairs,
                require_name=True,
                require_set_number_match=True,
            )
            _consume(
                result,
                set_number_candidates,
                remaining,
                required - result.owned_quantity,
                MatchStatus.SET_NUMBER,
            )

        if result.owned_quantity < required:
            name_candidates = _available_candidates(
                name_index.get(cube_card.normalised_name, []),
                cube_card,
                remaining,
                rejected_pairs,
                require_name=True,
            )
            _consume(
                result,
                name_candidates,
                remaining,
                required - result.owned_quantity,
                MatchStatus.NAME_ONLY,
            )

        result.missing_quantity = max(required - result.owned_quantity, 0)
        if result.allocations:
            if any(allocation.status == MatchStatus.NAME_ONLY for allocation in result.allocations):
                result.status = MatchStatus.NAME_ONLY
            elif any(
                allocation.status == MatchStatus.SET_NUMBER for allocation in result.allocations
            ):
                result.status = MatchStatus.SET_NUMBER
            else:
                result.status = MatchStatus.EXACT
        results.append(result)

    return sorted(results, key=lambda result: result.cube_card.id)


def _available_candidates(
    candidates: list[OwnedCardInput],
    cube_card: CubeCardInput,
    remaining: dict[int, int],
    rejected_pairs: set[tuple[str, str]],
    *,
    require_name: bool = False,
    require_number_match: bool = False,
    require_set_number_match: bool = False,
) -> list[OwnedCardInput]:
    return [
        owned
        for owned in candidates
        if remaining[owned.id] > 0
        and (not require_name or owned.normalised_name == cube_card.normalised_name)
        and (
            not require_number_match
            or (
                owned.collector_number
                and cube_card.collector_number
                and collector_numbers_match(owned.collector_number, cube_card.collector_number)
            )
        )
        and (
            not require_set_number_match
            or (
                owned.collector_number
                and cube_card.collector_number
                and collector_number_and_total_match(
                    owned.collector_number,
                    cube_card.collector_number,
                    cube_card.set_total,
                )
            )
        )
        and not _is_rejected(owned, cube_card, rejected_pairs)
    ]


def _consume(
    result: CubeCardAllocation,
    candidates: list[OwnedCardInput],
    remaining: dict[int, int],
    wanted: int,
    status: MatchStatus,
) -> None:
    for owned in sorted(candidates, key=lambda card: (card.original_name, card.id)):
        if wanted <= 0:
            return
        used = min(wanted, remaining[owned.id])
        if used <= 0:
            continue
        remaining[owned.id] -= used
        wanted -= used
        result.owned_quantity += used
        result.allocations.append(
            OwnedAllocation(
                owned_card_id=owned.id,
                original_name=owned.original_name,
                quantity=used,
                status=status,
            )
        )


def _is_rejected(
    owned: OwnedCardInput, cube_card: CubeCardInput, rejected_pairs: set[tuple[str, str]]
) -> bool:
    owned_sig = card_signature(owned.original_name, owned.set_code, owned.collector_number)
    cube_sig = card_signature(
        cube_card.original_name, cube_card.set_code, cube_card.collector_number
    )
    return (owned_sig, cube_sig) in rejected_pairs


def _looks_identifier_only(value: str) -> bool:
    return bool(value and "|" not in value and "-" in value and " " not in value.strip())
