import json
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
                tcgplayer_missing_market_cost=comparison.tcgplayer_missing_market_cost,
                cardmarket_missing_market_cost=comparison.cardmarket_missing_market_cost,
                priced_missing_copies=comparison.priced_missing_copies,
                unpriced_missing_copies=comparison.unpriced_missing_copies,
                cubekoga_likes=_cubekoga_like_count(comparison.cube),
            )
        )
    session.commit()
    return len(comparisons)


def _cubekoga_like_count(cube: Cube) -> int | None:
    try:
        raw = json.loads(cube.raw_source_data)
    except ValueError:
        return None
    metadata = raw.get("metadata")
    if not isinstance(metadata, dict):
        return None
    for key in ("cube_Like_Count", "cubeLikeCount", "likeCount", "likes"):
        value = metadata.get(key)
        if value is None or value == "":
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None
