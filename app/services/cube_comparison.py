import json
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CardMatchOverride, Cube, CubeCard, OwnedCard
from app.services.card_allocation import (
    CubeCardAllocation,
    CubeCardInput,
    MatchStatus,
    OwnedCardInput,
    allocate_cards,
)


@dataclass(frozen=True)
class CubeComparison:
    cube: Cube
    allocations: list[CubeCardAllocation]
    total_required_copies: int
    owned_required_copies: int
    missing_copies: int
    missing_unique_cards: int
    fulfilled_unique_cards: int
    total_unique_cards: int
    exact_matched_copies: int
    set_number_matched_copies: int
    name_only_matched_copies: int
    unresolved_match_count: int
    tcgplayer_missing_market_cost: float
    cardmarket_missing_market_cost: float
    priced_missing_copies: int
    unpriced_missing_copies: int

    @property
    def copy_completion(self) -> float:
        if self.total_required_copies == 0:
            return 0.0
        return self.owned_required_copies / self.total_required_copies

    @property
    def unique_completion(self) -> float:
        if self.total_unique_cards == 0:
            return 0.0
        return self.fulfilled_unique_cards / self.total_unique_cards

    @property
    def exact_completion(self) -> float:
        if self.total_required_copies == 0:
            return 0.0
        return self.exact_matched_copies / self.total_required_copies

    @property
    def name_only_completion(self) -> float:
        if self.total_required_copies == 0:
            return 0.0
        return self.name_only_matched_copies / self.total_required_copies


def compare_cube(session: Session, cube: Cube) -> CubeComparison:
    owned_cards = _owned_card_inputs(session)
    cube_cards = [
        _cube_card_input(card)
        for card in session.scalars(
            select(CubeCard).where(CubeCard.cube_id == cube.id).order_by(CubeCard.id)
        ).all()
    ]
    rejected = _rejected_pairs(session)
    allocations = allocate_cards(owned_cards, cube_cards, rejected_pairs=rejected)
    return build_comparison(cube, allocations)


def compare_cubes(session: Session, cubes: list[Cube]) -> list[CubeComparison]:
    if not cubes:
        return []
    owned_cards = _owned_card_inputs(session)
    rejected = _rejected_pairs(session)
    cube_ids = [cube.id for cube in cubes]
    cards_by_cube_id: dict[int, list[CubeCardInput]] = defaultdict(list)
    for card in session.scalars(
        select(CubeCard).where(CubeCard.cube_id.in_(cube_ids)).order_by(CubeCard.id)
    ):
        cards_by_cube_id[card.cube_id].append(_cube_card_input(card))
    return [
        build_comparison(
            cube,
            allocate_cards(
                owned_cards, cards_by_cube_id.get(cube.id, []), rejected_pairs=rejected
            ),
        )
        for cube in cubes
    ]


def _owned_card_inputs(session: Session) -> list[OwnedCardInput]:
    return [
        OwnedCardInput(
            id=card.id,
            original_name=card.original_name,
            normalised_name=card.normalised_name,
            set_code=card.set_code,
            collector_number=card.collector_number,
            quantity=card.quantity,
        )
        for card in session.scalars(select(OwnedCard).order_by(OwnedCard.id)).all()
    ]


def _cube_card_input(card: CubeCard) -> CubeCardInput:
    return CubeCardInput(
        id=card.id,
        original_name=card.original_name,
        normalised_name=card.normalised_name,
        set_name=card.set_name,
        set_code=card.set_code,
        collector_number=card.collector_number,
        set_total=_cube_set_total(card),
        required_quantity=card.required_quantity,
        tcgplayer_market_price=_cube_card_price(card, "tcgPlayerMarket"),
        cardmarket_market_price=_cube_card_price(card, "cardmarketMarket"),
    )


def _rejected_pairs(session: Session) -> set[tuple[str, str]]:
    return {
        (override.owned_card_signature, override.cube_card_signature)
        for override in session.scalars(select(CardMatchOverride)).all()
        if override.decision == "reject"
    }


def build_comparison(cube: Cube, allocations: list[CubeCardAllocation]) -> CubeComparison:
    total_required = sum(item.cube_card.required_quantity for item in allocations)
    owned_required = sum(item.owned_quantity for item in allocations)
    missing = sum(item.missing_quantity for item in allocations)
    exact = sum(
        allocation.quantity
        for item in allocations
        for allocation in item.allocations
        if allocation.status == MatchStatus.EXACT
    )
    name_only = sum(
        allocation.quantity
        for item in allocations
        for allocation in item.allocations
        if allocation.status == MatchStatus.NAME_ONLY
    )
    set_number = sum(
        allocation.quantity
        for item in allocations
        for allocation in item.allocations
        if allocation.status == MatchStatus.SET_NUMBER
    )
    fulfilled_unique = sum(1 for item in allocations if item.missing_quantity == 0)
    missing_unique = sum(1 for item in allocations if item.missing_quantity > 0)
    unresolved = sum(item.missing_quantity for item in allocations if item.missing_quantity > 0)
    tcgplayer_cost = 0.0
    cardmarket_cost = 0.0
    priced_missing = 0
    unpriced_missing = 0
    for item in allocations:
        if item.missing_quantity <= 0:
            continue
        if item.cube_card.tcgplayer_market_price is None:
            unpriced_missing += item.missing_quantity
        else:
            priced_missing += item.missing_quantity
            tcgplayer_cost += item.missing_quantity * item.cube_card.tcgplayer_market_price
        if item.cube_card.cardmarket_market_price is not None:
            cardmarket_cost += item.missing_quantity * item.cube_card.cardmarket_market_price
    return CubeComparison(
        cube=cube,
        allocations=allocations,
        total_required_copies=total_required,
        owned_required_copies=owned_required,
        missing_copies=missing,
        missing_unique_cards=missing_unique,
        fulfilled_unique_cards=fulfilled_unique,
        total_unique_cards=len(allocations),
        exact_matched_copies=exact,
        set_number_matched_copies=set_number,
        name_only_matched_copies=name_only,
        unresolved_match_count=unresolved,
        tcgplayer_missing_market_cost=tcgplayer_cost,
        cardmarket_missing_market_cost=cardmarket_cost,
        priced_missing_copies=priced_missing,
        unpriced_missing_copies=unpriced_missing,
    )


def _cube_set_total(card: CubeCard) -> str | None:
    try:
        raw = json.loads(card.raw_source_data)
    except ValueError:
        return None
    for key in (
        "set_Total",
        "setTotal",
        "printedTotal",
        "total",
        "set_Printed_Total",
        "setPrintedTotal",
        "set_Card_Count",
        "setCardCount",
    ):
        value = raw.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _cube_card_price(card: CubeCard, key: str) -> float | None:
    try:
        raw = json.loads(card.raw_source_data)
    except ValueError:
        return None
    value = raw.get(key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
