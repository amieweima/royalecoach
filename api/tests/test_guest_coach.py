"""The guest scouting flow: /coach/{tag} builds a report from a live battle
log without touching the database."""

import json

import pytest
from conftest import DECK_A, DECK_B
from fastapi.testclient import TestClient

import app.main as main
from app.clash_client import ClashApiError, normalize_tag


def test_normalize_tag():
    assert normalize_tag("#C8LVVCVJJ") == "#C8LVVCVJJ"
    assert normalize_tag("c8lvvcvjj") == "#C8LVVCVJJ"
    assert normalize_tag("  #c8lvvcvjj ") == "#C8LVVCVJJ"
    # letter O is not in the tag alphabet; players mean zero
    assert normalize_tag("oVo") == "#0V0"


def _cards(names):
    return [
        {"id": 26000000 + i, "name": n, "level": 11, "maxLevel": 14}
        for i, n in enumerate(names)
    ]


def _raw_battle(i: int, won: bool = True, battle_type: str = "pathOfLegend"):
    return {
        "battleTime": f"20260825T1{i % 10}0000.000Z",
        "type": battle_type,
        "gameMode": {"name": "Ranked1v1"},
        "team": [
            {
                "tag": "#GUEST",
                "name": "Guest",
                "crowns": 1 if won else 0,
                "startingTrophies": 7000,
                "cards": _cards(DECK_A),
            }
        ],
        "opponent": [
            {
                "tag": f"#OPP{i}",
                "name": "O",
                "crowns": 0 if won else 1,
                "startingTrophies": 7000,
                "cards": _cards(DECK_B),
            }
        ],
    }


@pytest.fixture()
def api(monkeypatch):
    """TestClient with the upstream Clash API stubbed out."""
    calls = {"n": 0}
    log = [_raw_battle(i, won=i % 2 == 0) for i in range(8)]
    log.append(_raw_battle(8, battle_type="friendly"))  # casual: must be excluded

    class FakeClient:
        def __init__(self, token):
            pass

        def battle_log(self, tag):
            calls["n"] += 1
            if tag == "#N0SUCH":
                raise ClashApiError("404: not found (/players/...) — check the tag.")
            return log

    monkeypatch.setattr("app.clash_client.ClashClient", FakeClient)
    main._guest_cache.clear()
    with TestClient(main.app) as client:
        yield client, calls


def test_guest_report(api):
    client, _ = api
    resp = client.get("/coach/guest")  # lowercase, no # — normalization applies
    assert resp.status_code == 200
    report = resp.json()
    assert report["player"] == {"tag": "#GUEST", "name": "Guest"}
    assert report["overall"]["n"] == 8  # the friendly is excluded
    assert report["overall"]["wins"] == 4
    assert len(report["deck"]) == 8
    assert all(c["underlevel"] == 3 for c in report["deck"])


def test_guest_report_cached(api):
    client, calls = api
    client.get("/coach/GUEST")
    client.get("/coach/%23guest")
    assert calls["n"] == 1  # same normalized tag: one upstream fetch


def test_guest_unknown_tag_404(api):
    client, _ = api
    resp = client.get("/coach/nosuch")
    assert resp.status_code == 404
