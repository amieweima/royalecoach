"""The self-ping that keeps the free Render instance from idling out."""

import httpx

import app.main as main


def test_ping_self_hits_health(monkeypatch):
    seen = []
    monkeypatch.setattr(httpx, "get", lambda url, timeout: seen.append(url))
    main._ping_self("https://example.onrender.com")
    assert seen == ["https://example.onrender.com/health"]


def test_ping_self_swallows_errors(monkeypatch):
    def boom(url, timeout):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", boom)
    main._ping_self("https://example.onrender.com")  # must not raise
