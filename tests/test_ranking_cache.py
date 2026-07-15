from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.models import Collection, Cube, CubeCard, CubeRanking, OwnedCard
from app.models.database_models import Base
from app.services.ranking_cache import load_saved_rankings, refresh_saved_rankings


def test_refresh_saved_rankings_persists_dashboard_results() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with session_factory() as session:
        collection = Collection(name="Mine", source_filename="collection.csv")
        session.add(collection)
        session.flush()
        session.add(
            OwnedCard(
                collection_id=collection.id,
                original_name="Pikachu",
                normalised_name="pikachu",
                set_name=None,
                normalised_set_name=None,
                set_code=None,
                collector_number=None,
                quantity=1,
                printing=None,
                condition=None,
                raw_import_data="{}",
            )
        )
        cube = Cube(name="Electric Cube", source_type="manual", raw_source_data="{}")
        session.add(cube)
        session.flush()
        session.add(
            CubeCard(
                cube_id=cube.id,
                original_name="Pikachu",
                normalised_name="pikachu",
                set_name=None,
                set_code=None,
                collector_number=None,
                required_quantity=2,
                raw_source_data='{"tcgPlayerMarket": 3.25, "cardmarketMarket": 2.5}',
            )
        )
        session.commit()

        refreshed = refresh_saved_rankings(session)
        saved, computed_at = load_saved_rankings(session)

        assert refreshed == 1
        assert computed_at is not None
        assert len(saved) == 1
        assert saved[0].cube.name == "Electric Cube"
        assert saved[0].owned_required_copies == 1
        assert saved[0].missing_copies == 1
        assert saved[0].tcgplayer_missing_market_cost == 3.25
        assert saved[0].cardmarket_missing_market_cost == 2.5
        assert saved[0].priced_missing_copies == 1
        assert saved[0].unpriced_missing_copies == 0

        refreshed_again = refresh_saved_rankings(session)
        saved_again, _ = load_saved_rankings(session)

        assert refreshed_again == 1
        assert len(saved_again) == 1
        assert session.scalar(select(func.count()).select_from(CubeRanking)) == 1
