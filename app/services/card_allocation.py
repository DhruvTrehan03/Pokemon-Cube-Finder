from dataclasses import dataclass, field
from enum import StrEnum

from app.services.card_normalisation import card_signature


class MatchStatus(StrEnum):
    EXACT = "exact"
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
    remaining = {card.id: max(card.quantity, 0) for card in owned_cards}
    results: list[CubeCardAllocation] = []

    for cube_card in sorted(cube_cards, key=lambda card: (card.normalised_name, card.id)):
        required = max(cube_card.required_quantity, 0)
        result = CubeCardAllocation(
            cube_card=cube_card,
            missing_quantity=required,
        )

        exact_candidates = [
            owned
            for owned in owned_cards
            if remaining[owned.id] > 0
            and owned.normalised_name == cube_card.normalised_name
            and owned.set_code
            and cube_card.set_code
            and owned.collector_number
            and cube_card.collector_number
            and owned.set_code == cube_card.set_code
            and owned.collector_number == cube_card.collector_number
            and not _is_rejected(owned, cube_card, rejected_pairs)
        ]
        _consume(result, exact_candidates, remaining, required, MatchStatus.EXACT)

        if result.owned_quantity < required:
            name_candidates = [
                owned
                for owned in owned_cards
                if remaining[owned.id] > 0
                and owned.normalised_name == cube_card.normalised_name
                and not _is_rejected(owned, cube_card, rejected_pairs)
            ]
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
            else:
                result.status = MatchStatus.EXACT
        results.append(result)

    return sorted(results, key=lambda result: result.cube_card.id)


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
