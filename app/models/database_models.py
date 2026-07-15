from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="My Collection")
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    source_filename: Mapped[str | None] = mapped_column(String(300))

    cards: Mapped[list["OwnedCard"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )


class OwnedCard(Base):
    __tablename__ = "owned_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(300), index=True)
    normalised_name: Mapped[str] = mapped_column(String(300), index=True)
    set_name: Mapped[str | None] = mapped_column(String(200))
    normalised_set_name: Mapped[str | None] = mapped_column(String(200), index=True)
    set_code: Mapped[str | None] = mapped_column(String(40), index=True)
    collector_number: Mapped[str | None] = mapped_column(String(80), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    printing: Mapped[str | None] = mapped_column(String(120))
    condition: Mapped[str | None] = mapped_column(String(80))
    raw_import_data: Mapped[str] = mapped_column(Text, default="{}")

    collection: Mapped[Collection] = relationship(back_populates="cards")


class Cube(Base):
    __tablename__ = "cubes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    author: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(80), default="manual")
    source_url: Mapped[str | None] = mapped_column(String(800), index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime)
    raw_source_data: Mapped[str] = mapped_column(Text, default="{}")

    cards: Mapped[list["CubeCard"]] = relationship(
        back_populates="cube", cascade="all, delete-orphan"
    )


class CubeCard(Base):
    __tablename__ = "cube_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cube_id: Mapped[int] = mapped_column(ForeignKey("cubes.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(300), index=True)
    normalised_name: Mapped[str] = mapped_column(String(300), index=True)
    set_name: Mapped[str | None] = mapped_column(String(200))
    set_code: Mapped[str | None] = mapped_column(String(40), index=True)
    collector_number: Mapped[str | None] = mapped_column(String(80), index=True)
    required_quantity: Mapped[int] = mapped_column(Integer, default=1)
    raw_source_data: Mapped[str] = mapped_column(Text, default="{}")

    cube: Mapped[Cube] = relationship(back_populates="cards")


class CubeRanking(Base):
    __tablename__ = "cube_rankings"
    __table_args__ = (UniqueConstraint("cube_id", name="uq_cube_rankings_cube_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cube_id: Mapped[int] = mapped_column(ForeignKey("cubes.id"), index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    total_required_copies: Mapped[int] = mapped_column(Integer, default=0)
    owned_required_copies: Mapped[int] = mapped_column(Integer, default=0)
    missing_copies: Mapped[int] = mapped_column(Integer, default=0)
    missing_unique_cards: Mapped[int] = mapped_column(Integer, default=0)
    fulfilled_unique_cards: Mapped[int] = mapped_column(Integer, default=0)
    total_unique_cards: Mapped[int] = mapped_column(Integer, default=0)
    exact_matched_copies: Mapped[int] = mapped_column(Integer, default=0)
    set_number_matched_copies: Mapped[int] = mapped_column(Integer, default=0)
    name_only_matched_copies: Mapped[int] = mapped_column(Integer, default=0)
    unresolved_match_count: Mapped[int] = mapped_column(Integer, default=0)
    tcgplayer_missing_market_cost: Mapped[float] = mapped_column(Float, default=0.0)
    cardmarket_missing_market_cost: Mapped[float] = mapped_column(Float, default=0.0)
    priced_missing_copies: Mapped[int] = mapped_column(Integer, default=0)
    unpriced_missing_copies: Mapped[int] = mapped_column(Integer, default=0)

    cube: Mapped[Cube] = relationship()

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


class CardMatchOverride(Base):
    __tablename__ = "card_match_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owned_card_signature: Mapped[str] = mapped_column(String(500), index=True)
    cube_card_signature: Mapped[str] = mapped_column(String(500), index=True)
    decision: Mapped[str] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
