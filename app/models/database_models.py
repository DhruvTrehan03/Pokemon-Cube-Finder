from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
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


class CardMatchOverride(Base):
    __tablename__ = "card_match_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owned_card_signature: Mapped[str] = mapped_column(String(500), index=True)
    cube_card_signature: Mapped[str] = mapped_column(String(500), index=True)
    decision: Mapped[str] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
