import json
from datetime import datetime

from ..models import Battle

# API timestamps look like "20260830T142530.000Z"
TIME_FMT = "%Y%m%dT%H%M%S.%fZ"


def parse_battle_time(s: str) -> datetime:
    return datetime.strptime(s, TIME_FMT)


def _deck(cards: list[dict]) -> str:
    return json.dumps(
        [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "level": c.get("level"),
                "maxLevel": c.get("maxLevel"),
            }
            for c in cards
        ]
    )


def battle_to_row(battle: dict, source: str) -> Battle | None:
    """Convert one battle-log entry into a Battle row, or None if it isn't a
    usable 1v1 (2v2s, boat battles, draws, and modes without decks are skipped)."""
    team = battle.get("team") or []
    opp = battle.get("opponent") or []
    if len(team) != 1 or len(opp) != 1:
        return None
    me, them = team[0], opp[0]
    if not me.get("cards") or not them.get("cards"):
        return None
    if me.get("crowns", 0) == them.get("crowns", 0):
        return None  # draw

    uid = f"{battle['battleTime']}:{me['tag']}:{them['tag']}"
    return Battle(
        uid=uid,
        battle_time=parse_battle_time(battle["battleTime"]),
        battle_type=battle.get("type", ""),
        game_mode=(battle.get("gameMode") or {}).get("name", ""),
        source=source,
        player_tag=me["tag"],
        player_name=me.get("name", ""),
        player_trophies=me.get("startingTrophies"),
        player_crowns=me.get("crowns", 0),
        player_trophy_change=me.get("trophyChange"),
        player_elixir_leaked=me.get("elixirLeaked"),
        player_deck_json=_deck(me["cards"]),
        opponent_tag=them["tag"],
        opponent_name=them.get("name", ""),
        opponent_trophies=them.get("startingTrophies"),
        opponent_crowns=them.get("crowns", 0),
        opponent_deck_json=_deck(them["cards"]),
        won=1 if me.get("crowns", 0) > them.get("crowns", 0) else 0,
        raw_json=json.dumps(battle),
    )


def insert_new(session, rows: list[Battle]) -> int:
    """Insert rows whose uid isn't already stored. Returns number inserted."""
    if not rows:
        return 0
    existing = {
        uid
        for (uid,) in session.query(Battle.uid)
        .filter(Battle.uid.in_([r.uid for r in rows]))
        .all()
    }
    new = [r for r in rows if r.uid not in existing]
    session.add_all(new)
    session.commit()
    return len(new)
