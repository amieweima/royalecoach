"""Personal coaching insights from your banked battles (source="me").

    python -m app.ml.coach

Everything here is deliberately transparent statistics over your own history —
win rates with sample sizes attached — so the dashboard can show receipts, not
just verdicts. Small-n results are reported with their n; the caller decides
what to trust.
"""

import json
from datetime import timedelta

from sqlalchemy.orm import Session

from ..db import SessionLocal, init_db
from ..models import Battle

SESSION_GAP = timedelta(minutes=30)  # a gap this long starts a new play session
MIN_MATCHUP_N = 5


def my_battles(session: Session) -> list[Battle]:
    return (
        session.query(Battle)
        .filter(Battle.source == "me")
        .order_by(Battle.battle_time)
        .all()
    )


def overall_win_rate(battles: list[Battle]) -> dict:
    n = len(battles)
    wins = sum(b.won for b in battles)
    return {"n": n, "wins": wins, "win_rate": wins / n if n else None}


def matchup_report(battles: list[Battle], min_n: int = MIN_MATCHUP_N) -> list[dict]:
    """Win rate when the opponent runs each card, worst matchups first."""
    overall = overall_win_rate(battles)["win_rate"] or 0.0
    stats: dict[str, list[int]] = {}  # card -> [n, wins]
    for b in battles:
        for card in {c.get("name") for c in json.loads(b.opponent_deck_json)}:
            s = stats.setdefault(card, [0, 0])
            s[0] += 1
            s[1] += b.won
    out = [
        {
            "card": card,
            "n": n,
            "win_rate": wins / n,
            "delta_vs_overall": wins / n - overall,
        }
        for card, (n, wins) in stats.items()
        if n >= min_n
    ]
    return sorted(out, key=lambda r: r["win_rate"])


def underlevel_report(battles: list[Battle]) -> list[dict]:
    """Your cards that are below max level, with your win rate when playing them."""
    stats: dict[str, dict] = {}
    for b in battles:
        for c in json.loads(b.player_deck_json):
            under = (c.get("maxLevel") or 0) - (c.get("level") or 0)
            if under <= 0:
                continue
            s = stats.setdefault(c.get("name"), {"n": 0, "wins": 0, "underlevel": under})
            s["n"] += 1
            s["wins"] += b.won
            s["underlevel"] = max(s["underlevel"], under)
    out = [
        {"card": card, "underlevel": s["underlevel"], "n": s["n"],
         "win_rate": s["wins"] / s["n"]}
        for card, s in stats.items()
    ]
    return sorted(out, key=lambda r: (-r["underlevel"], -r["n"]))


def _sessions(battles: list[Battle]) -> list[list[Battle]]:
    sessions: list[list[Battle]] = []
    for b in battles:
        if sessions and b.battle_time - sessions[-1][-1].battle_time <= SESSION_GAP:
            sessions[-1].append(b)
        else:
            sessions.append([b])
    return sessions


def tilt_report(battles: list[Battle]) -> dict:
    """Within-session momentum: do losses beget losses, and do long sessions decay?"""
    after_win = [0, 0]  # [n, wins]
    after_loss = [0, 0]
    after_two_losses = [0, 0]
    early = [0, 0]  # battles 1-5 of a session
    late = [0, 0]  # battle 6 onward

    for sess in _sessions(battles):
        for i, b in enumerate(sess):
            bucket = early if i < 5 else late
            bucket[0] += 1
            bucket[1] += b.won
            if i >= 1:
                prev = after_win if sess[i - 1].won else after_loss
                prev[0] += 1
                prev[1] += b.won
            if i >= 2 and not sess[i - 1].won and not sess[i - 2].won:
                after_two_losses[0] += 1
                after_two_losses[1] += b.won

    def rate(pair):
        return {"n": pair[0], "win_rate": pair[1] / pair[0] if pair[0] else None}

    return {
        "sessions": len(_sessions(battles)),
        "after_win": rate(after_win),
        "after_loss": rate(after_loss),
        "after_two_losses": rate(after_two_losses),
        "session_battles_1_to_5": rate(early),
        "session_battles_6_plus": rate(late),
    }


def full_report(session: Session) -> dict:
    battles = my_battles(session)
    if not battles:
        return {"error": "No personal battles banked yet — run the poller."}
    return {
        "overall": overall_win_rate(battles),
        "worst_matchups": matchup_report(battles),
        "underleveled_cards": underlevel_report(battles),
        "tilt": tilt_report(battles),
    }


def main() -> None:
    init_db()
    with SessionLocal() as s:
        print(json.dumps(full_report(s), indent=2, default=str))


if __name__ == "__main__":
    main()
