import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.adapters.cube_sources.base import ImportedCube, ImportedCubeCard
from app.main import _backfill_cubekoga_source_urls, save_imported_cube
from app.models import Cube, CubeCard
from app.models.database_models import Base


def test_bulk_cubekoga_import_updates_existing_cube_by_canonical_url() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with session_factory() as session:
        session.add(
            Cube(
                name="Old Name",
                author="Old Author",
                source_type="cubekoga",
                source_url="https://cubekoga.net/cube/noahsark",
                raw_source_data=json.dumps({"metadata": {"cube_ID": 42}}),
            )
        )
        session.commit()

        _backfill_cubekoga_source_urls(session)
        imported = ImportedCube(
            name="New Name",
            author="New Author",
            source_type="cubekoga",
            source_url="https://cubekoga.net/cube/42",
            cards=[ImportedCubeCard(name="Pikachu", quantity=2)],
            raw_source_data={"metadata": {"cube_ID": 42}, "cards": []},
        )

        cube = save_imported_cube(session, imported, scan_cubekoga_id=False)

        cubes = session.scalars(select(Cube)).all()
        cards = session.scalars(select(CubeCard)).all()
        assert len(cubes) == 1
        assert cube.id == cubes[0].id
        assert cube.name == "New Name"
        assert cube.author == "New Author"
        assert cube.source_url == "https://cubekoga.net/cube/42"
        assert len(cards) == 1
        assert cards[0].required_quantity == 2
