from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Cube, CubeRanking
from app.services.cube_comparison import compare_cubes


def load_saved_rankings(session: Session) -> tuple[list[CubeRanking], datetime | None]:
    rankings = session.scalars(
        select(CubeRanking)
        .options(selectinload(CubeRanking.cube))
        .join(Cube)
        .order_by(Cube.name)
    ).all()
    computed_at = session.scalar(select(func.max(CubeRanking.computed_at)))
    return list(rankings), computed_at


def refresh_saved_rankings(session: Session) -> int:
    cubes = session.scalars(select(Cube).order_by(Cube.name)).all()
    comparisons = compare_cubes(session, list(cubes))
    computed_at = datetime.utcnow()
    session.execute(delete(CubeRanking))
    for comparison in comparisons:
        session.add(
            CubeRanking(
                cube_id=comparison.cube.id,
                computed_at=computed_at,
                total_required_copies=comparison.total_required_copies,
                owned_required_copies=comparison.owned_required_copies,
                missing_copies=comparison.missing_copies,
                missing_unique_cards=comparison.missing_unique_cards,
                fulfilled_unique_cards=comparison.fulfilled_unique_cards,
                total_unique_cards=comparison.total_unique_cards,
                exact_matched_copies=comparison.exact_matched_copies,
                set_number_matched_copies=comparison.set_number_matched_copies,
                name_only_matched_copies=comparison.name_only_matched_copies,
                unresolved_match_count=comparison.unresolved_match_count,
            )
        )
    session.commit()
    return len(comparisons)
