from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.database_models import Base, CubeCard, OwnedCard
from app.services.card_normalisation import (
    clean_display_card_name,
    derive_set_code,
    normalise_set_code,
    normalise_card_name,
    parse_card_identifier,
)


engine = create_engine(
    get_settings().database_url,
    connect_args={"check_same_thread": False}
    if get_settings().database_url.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    backfill_normalised_identifiers()


def backfill_normalised_identifiers() -> None:
    with SessionLocal() as session:
        changed = False
        for card in session.query(OwnedCard).all():
            cleaned_name = clean_display_card_name(card.original_name)
            derived_set_code = card.set_code or derive_set_code(card.set_name)
            normalised_name = normalise_card_name(cleaned_name)
            if card.original_name != cleaned_name:
                card.original_name = cleaned_name
                changed = True
            if card.normalised_name != normalised_name:
                card.normalised_name = normalised_name
                changed = True
            if derived_set_code and card.set_code != derived_set_code:
                card.set_code = derived_set_code
                changed = True
            if (
                card.set_name
                and not derived_set_code
                and card.set_code == normalise_set_code(card.set_name)
            ):
                card.set_code = None
                changed = True

        for card in session.query(CubeCard).all():
            parsed_set_code, parsed_number = parse_card_identifier(card.original_name)
            if parsed_set_code and not card.set_code:
                card.set_code = parsed_set_code
                changed = True
            if parsed_number and not card.collector_number:
                card.collector_number = parsed_number
                changed = True
        if changed:
            session.commit()


async def get_session() -> AsyncGenerator[Session, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
