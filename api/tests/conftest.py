import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base  # noqa: E402
from app.models import Battle  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


def deck_json(names: list[str], level: int = 14, max_level: int = 14) -> str:
    return json.dumps(
        [
            {"id": 26000000 + i, "name": n, "level": level, "maxLevel": max_level}
            for i, n in enumerate(names)
        ]
    )


DECK_A = ["Hog Rider", "Fireball", "Musketeer", "Cannon", "Skeletons", "Ice Spirit", "Log", "Ice Golem"]
DECK_B = ["Golem", "Night Witch", "Baby Dragon", "Lumberjack", "Tornado", "Lightning", "Mega Minion", "Barbarian Barrel"]


def make_battle(
    i: int,
    won: int = 1,
    p_deck: str | None = None,
    o_deck: str | None = None,
    p_tag: str = "#PLAYER",
    o_tag: str = "#OPP",
    p_trophies: int = 7000,
    o_trophies: int = 7000,
    when: datetime | None = None,
    source: str = "ladder",
) -> Battle:
    when = when or (datetime(2026, 8, 1) + timedelta(minutes=i))
    return Battle(
        uid=f"{when.isoformat()}:{p_tag}:{o_tag}",
        battle_time=when,
        battle_type="pathOfLegend",
        game_mode="Ranked1v1_NewArena2",
        source=source,
        player_tag=p_tag,
        player_name="P",
        player_trophies=p_trophies,
        player_crowns=1 if won else 0,
        player_trophy_change=None,
        player_elixir_leaked=None,
        player_deck_json=p_deck or deck_json(DECK_A),
        opponent_tag=o_tag,
        opponent_name="O",
        opponent_trophies=o_trophies,
        opponent_crowns=0 if won else 1,
        opponent_deck_json=o_deck or deck_json(DECK_B),
        won=won,
        raw_json="{}",
    )
