"""Turn banked battles into a model-ready feature matrix.

Features are strictly pre-battle information (decks, card levels, trophies).
In-battle stats like crowns or elixir leaked are excluded here — they leak the
outcome — but stay available for post-hoc coaching analysis.
"""

import json

import pandas as pd
from sqlalchemy.orm import Session

from ..models import Battle

# Cards rarer than this (fraction of battles) are dropped from the vocabulary
# so the matrix doesn't fill with near-constant columns.
MIN_CARD_FREQ = 0.01


def _underlevels(deck: list[dict]) -> list[int]:
    """How far below max each card is (0 = maxed)."""
    return [
        (c.get("maxLevel") or 0) - (c.get("level") or 0)
        for c in deck
    ]


def battles_to_frame(session: Session, source: str | None = None) -> pd.DataFrame:
    """Load battles into a tidy frame, one row per unique battle.

    Harvested data can contain the same battle from both players'
    perspectives (mirrored label); we keep only the first perspective seen
    so a random or time split can't put the two mirrors on opposite sides.
    """
    q = session.query(Battle).order_by(Battle.battle_time)
    if source is not None:
        q = q.filter(Battle.source == source)

    rows = []
    seen_pairs: set[str] = set()
    for b in q:
        pair = f"{b.battle_time.isoformat()}:" + ":".join(
            sorted([b.player_tag, b.opponent_tag])
        )
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        p_deck = json.loads(b.player_deck_json)
        o_deck = json.loads(b.opponent_deck_json)
        p_under = _underlevels(p_deck)
        o_under = _underlevels(o_deck)
        rows.append(
            {
                "uid": b.uid,
                "battle_time": b.battle_time,
                "player_tag": b.player_tag,
                "trophy_diff": (b.player_trophies or 0) - (b.opponent_trophies or 0),
                "p_cards": [c.get("name") for c in p_deck],
                "o_cards": [c.get("name") for c in o_deck],
                "p_underlevel_mean": sum(p_under) / len(p_under),
                "p_underlevel_max": max(p_under),
                "o_underlevel_mean": sum(o_under) / len(o_under),
                "o_underlevel_max": max(o_under),
                "won": b.won,
            }
        )
    return pd.DataFrame(rows)


def card_vocabulary(frame: pd.DataFrame, min_freq: float = MIN_CARD_FREQ) -> list[str]:
    """Cards that appear (on either side) in at least `min_freq` of battles."""
    counts: dict[str, int] = {}
    for col in ("p_cards", "o_cards"):
        for deck in frame[col]:
            for name in set(deck):
                counts[name] = counts.get(name, 0) + 1
    cutoff = min_freq * len(frame)
    return sorted(name for name, n in counts.items() if n >= cutoff)


def make_matrix(
    frame: pd.DataFrame, vocab: list[str]
) -> tuple[pd.DataFrame, pd.Series]:
    """Build (X, y). Columns: numeric deltas + multi-hot deck membership."""
    cols: dict[str, pd.Series] = {
        "trophy_diff": frame["trophy_diff"],
        "p_underlevel_mean": frame["p_underlevel_mean"],
        "p_underlevel_max": frame["p_underlevel_max"],
        "o_underlevel_mean": frame["o_underlevel_mean"],
        "o_underlevel_max": frame["o_underlevel_max"],
        "underlevel_mean_diff": frame["p_underlevel_mean"] - frame["o_underlevel_mean"],
    }

    p_sets = frame["p_cards"].map(set)
    o_sets = frame["o_cards"].map(set)
    for name in vocab:
        cols[f"p::{name}"] = p_sets.map(lambda s: int(name in s))
        cols[f"o::{name}"] = o_sets.map(lambda s: int(name in s))

    return pd.DataFrame(cols, index=frame.index), frame["won"].astype(int)
