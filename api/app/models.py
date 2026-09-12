from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Battle(Base):
    """One 1v1 battle, stored from the perspective of `player_tag`."""

    __tablename__ = "battles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # battleTime + both tags uniquely identify a battle from one perspective
    uid: Mapped[str] = mapped_column(String(80), unique=True)
    battle_time: Mapped[datetime] = mapped_column(DateTime)
    battle_type: Mapped[str] = mapped_column(String(40))
    game_mode: Mapped[str] = mapped_column(String(60))
    # "me" = collected from MY_PLAYER_TAG's log, "ladder" = harvested from top players
    source: Mapped[str] = mapped_column(String(10))

    player_tag: Mapped[str] = mapped_column(String(16))
    player_name: Mapped[str] = mapped_column(String(40))
    player_trophies: Mapped[int | None] = mapped_column(Integer, nullable=True)
    player_crowns: Mapped[int] = mapped_column(Integer)
    player_trophy_change: Mapped[int | None] = mapped_column(Integer, nullable=True)
    player_elixir_leaked: Mapped[float | None] = mapped_column(nullable=True)
    player_deck_json: Mapped[str] = mapped_column(Text)

    opponent_tag: Mapped[str] = mapped_column(String(16))
    opponent_name: Mapped[str] = mapped_column(String(40))
    opponent_trophies: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opponent_crowns: Mapped[int] = mapped_column(Integer)
    opponent_deck_json: Mapped[str] = mapped_column(Text)

    won: Mapped[int] = mapped_column(Integer)  # 1 win, 0 loss (draws excluded)
    raw_json: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        Index("ix_battles_player_time", "player_tag", "battle_time"),
        Index("ix_battles_source", "source"),
    )


class PlayerSeen(Base):
    """Crawl frontier for the harvester: players we know about and when we
    last pulled their battle log."""

    __tablename__ = "players_seen"

    tag: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(10))  # "ranking" | "opponent"
    last_harvested: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
