"""Poll MY_PLAYER_TAG's battle log and bank new battles.

The API only exposes a rolling window of ~25 recent battles, so this runs on a
loop to accumulate history over time.

    python -m app.ingest.poller            # one pass
    python -m app.ingest.poller --loop     # poll every 10 min (Ctrl+C to stop)
"""

import argparse
import time
from datetime import datetime

from .. import config
from ..clash_client import ClashClient
from ..db import SessionLocal, init_db
from .parse import battle_to_row, insert_new


def run_once(client: ClashClient, tag: str) -> int:
    rows = [
        r
        for b in client.battle_log(tag)
        if (r := battle_to_row(b, source="me")) is not None
    ]
    with SessionLocal() as session:
        return insert_new(session, rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=600, help="seconds between polls")
    args = parser.parse_args()

    if not config.MY_TAG or config.MY_TAG.startswith("#X"):
        raise SystemExit("Set MY_PLAYER_TAG in .env first (copy .env.example).")

    init_db()
    client = ClashClient(config.API_TOKEN)
    while True:
        n = run_once(client, config.MY_TAG)
        print(f"[{datetime.now():%H:%M:%S}] {config.MY_TAG}: {n} new battle(s)")
        if not args.loop:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
