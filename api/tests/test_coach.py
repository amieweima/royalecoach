from datetime import datetime, timedelta

from conftest import DECK_A, DECK_B, deck_json, make_battle

from app.ml.coach import (
    matchup_report,
    my_battles,
    tilt_report,
    underlevel_report,
)

GOLEM_DECK = deck_json(DECK_B)  # contains "Golem"
CYCLE_DECK = deck_json(["Miner", "Poison", "Bats", "Goblins", "Spear Goblins", "Guards", "Tesla", "Zap"])


def test_matchup_report_finds_weakness(session):
    battles = []
    # Lose every game against Golem decks, win everything else.
    for i in range(10):
        battles.append(make_battle(i, won=0, o_deck=GOLEM_DECK, source="me"))
    for i in range(10, 20):
        battles.append(make_battle(i, won=1, o_deck=CYCLE_DECK, source="me"))
    session.add_all(battles)
    session.commit()

    report = matchup_report(my_battles(session))
    worst = report[0]
    assert worst["win_rate"] == 0.0
    assert worst["n"] == 10
    assert worst["delta_vs_overall"] == -0.5
    golem_cards = {r["card"] for r in report if r["win_rate"] == 0.0}
    assert "Golem" in golem_cards


def test_underlevel_report(session):
    under_deck = deck_json(DECK_A, level=12, max_level=14)
    session.add_all(
        [make_battle(i, won=i % 2, p_deck=under_deck, source="me") for i in range(4)]
    )
    session.commit()

    report = underlevel_report(my_battles(session))
    assert len(report) == len(DECK_A)
    assert all(r["underlevel"] == 2 and r["n"] == 4 for r in report)


def test_tilt_report_sessions_and_streaks(session):
    base = datetime(2026, 8, 20, 18, 0)
    battles = []
    # Session 1: W L L L — every battle after a loss is a loss.
    for i, won in enumerate([1, 0, 0, 0]):
        battles.append(make_battle(i, won=won, when=base + timedelta(minutes=5 * i), source="me"))
    # Session 2 (next day): W W — battle after a win is a win.
    for i, won in enumerate([1, 1]):
        battles.append(
            make_battle(100 + i, won=won, when=base + timedelta(days=1, minutes=5 * i), source="me")
        )
    session.add_all(battles)
    session.commit()

    tilt = tilt_report(my_battles(session))
    assert tilt["sessions"] == 2
    assert tilt["after_win"] == {"n": 2, "win_rate": 0.5}  # W->L (s1), W->W (s2)
    assert tilt["after_loss"] == {"n": 2, "win_rate": 0.0}
    assert tilt["after_two_losses"] == {"n": 1, "win_rate": 0.0}
