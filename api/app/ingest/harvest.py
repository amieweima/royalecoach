"""Harvest battles from top-ladder players to build the global training set.

Seeds the crawl frontier from the global rankings, pulls each player's battle
log, and enqueues the opponents it sees so later passes can crawl outward.
Safe to re-run any time; battles are deduped by uid.

    python -m app.ingest.harvest                     # 100 players per pass
    python -m app.ingest.harvest --max-players 300
"""

import argparse
from datetime import datetime, timezone

from .. import config
from ..clash_client import ClashClient
from ..db import SessionLocal, init_db
from ..models import PlayerSeen
from .parse import battle_to_row, insert_new


def seed_rankings(session, client: ClashClient, limit: int) -> int:
    added = 0
    for p in client.top_players(limit=limit):
        if not session.get(PlayerSeen, p["tag"]):
            session.add(
                PlayerSeen(
                    tag=p["tag"],
                    name=p.get("name", ""),
                    rating=p.get("eloRating") or p.get("trophies"),
                    source="ranking",
                )
            )
            added += 1
    session.commit()
    return added


def harvest_player(session, client: ClashClient, player: PlayerSeen) -> int:
    rows = []
    # collected by tag first: the same opponent can appear several times in one
    # battle log (rematches), and session.get can't see pending inserts
    new_opponents: dict[str, str] = {}
    for b in client.battle_log(player.tag):
        row = battle_to_row(b, source="ladder")
        if row is None:
            continue
        rows.append(row)
        opp_tag = row.opponent_tag
        if opp_tag and opp_tag not in new_opponents and not session.get(PlayerSeen, opp_tag):
            new_opponents[opp_tag] = row.opponent_name
    for tag, name in new_opponents.items():
        session.add(PlayerSeen(tag=tag, name=name, source="opponent"))
    inserted = insert_new(session, rows)
    player.last_harvested = datetime.now(timezone.utc).replace(tzinfo=None)
    session.commit()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-players", type=int, default=100)
    parser.add_argument("--seed-limit", type=int, default=100)
    args = parser.parse_args()

    init_db()
    client = ClashClient(config.API_TOKEN)

    with SessionLocal() as session:
        added = seed_rankings(session, client, args.seed_limit)
        print(f"rankings: {added} new player(s) added to frontier")

        # never-harvested first (rankings before opponents), then stalest
        frontier = (
            session.query(PlayerSeen)
            .order_by(
                PlayerSeen.last_harvested.isnot(None),
                PlayerSeen.source.desc(),  # "ranking" > "opponent"
                PlayerSeen.last_harvested,
            )
            .limit(args.max_players)
            .all()
        )

        total = 0
        for i, player in enumerate(frontier, 1):
            tag = player.tag  # grab before a rollback can expire the object
            try:
                n = harvest_player(session, client, player)
            except Exception as e:  # keep crawling past individual failures
                session.rollback()
                print(f"  ! {tag}: {e}")
                continue
            total += n
            if i % 10 == 0 or i == len(frontier):
                print(f"  [{i}/{len(frontier)}] +{total} battles so far")

        print(f"done: {total} new battle(s) this pass")


if __name__ == "__main__":
    main()
