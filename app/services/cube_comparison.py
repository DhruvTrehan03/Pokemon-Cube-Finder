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
    name_only_matched_copies: int
    unresolved_match_count: int

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
    owned_cards = [
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
    cube_cards = [
        CubeCardInput(
            id=card.id,
            original_name=card.original_name,
            normalised_name=card.normalised_name,
            set_name=card.set_name,
            set_code=card.set_code,
            collector_number=card.collector_number,
            required_quantity=card.required_quantity,
        )
        for card in session.scalars(
            select(CubeCard).where(CubeCard.cube_id == cube.id).order_by(CubeCard.id)
        ).all()
    ]
    rejected = {
        (override.owned_card_signature, override.cube_card_signature)
        for override in session.scalars(select(CardMatchOverride)).all()
        if override.decision == "reject"
    }
    allocations = allocate_cards(owned_cards, cube_cards, rejected_pairs=rejected)
    return build_comparison(cube, allocations)


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
    fulfilled_unique = sum(1 for item in allocations if item.missing_quantity == 0)
    missing_unique = sum(1 for item in allocations if item.missing_quantity > 0)
    unresolved = sum(item.missing_quantity for item in allocations if item.missing_quantity > 0)
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
        name_only_matched_copies=name_only,
        unresolved_match_count=unresolved,
    )
