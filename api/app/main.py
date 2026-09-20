import os
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func

from .db import SessionLocal, init_db
from .ml.coach import full_report
from .models import Battle, PlayerSeen

app = FastAPI(title="RoyaleCoach API")

# comma-separated origins; in prod set ALLOWED_ORIGINS to the dashboard URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "600"))


def _poll_forever() -> None:
    """In-process poller for deployments where a separate loop process isn't
    available (single web service). Enabled with ENABLE_POLLER=1."""
    from . import config
    from .clash_client import ClashClient
    from .ingest.poller import run_once

    client = ClashClient(config.API_TOKEN)
    while True:
        try:
            n = run_once(client, config.MY_TAG)
            if n:
                print(f"poller: {n} new battle(s)")
        except Exception as e:  # keep polling through transient API errors
            print(f"poller error: {e}")
        time.sleep(POLL_INTERVAL)


KEEPALIVE_INTERVAL = int(os.getenv("KEEPALIVE_INTERVAL_SECONDS", "600"))


def _ping_self(base_url: str) -> None:
    import httpx

    try:
        httpx.get(f"{base_url}/health", timeout=10)
    except Exception as e:  # a missed ping only risks a nap; never crash the thread
        print(f"keepalive error: {e}")


def _keepalive_forever(base_url: str) -> None:
    """Render's free tier spins the service down after 15 min without inbound
    traffic, and the next visitor eats a ~1 min cold start. A request to our
    own public URL counts as inbound, so the instance never goes idle. This
    can't wake an instance that is already asleep (a deploy, a restart) —
    .github/workflows/keepalive.yml covers that from the outside."""
    while True:
        time.sleep(KEEPALIVE_INTERVAL)
        _ping_self(base_url)


@app.on_event("startup")
def startup() -> None:
    init_db()
    if os.getenv("ENABLE_POLLER") == "1":
        threading.Thread(target=_poll_forever, daemon=True).start()
    # Render sets RENDER_EXTERNAL_URL on web services; unset locally -> no-op
    if base_url := os.getenv("RENDER_EXTERNAL_URL"):
        threading.Thread(
            target=_keepalive_forever, args=(base_url,), daemon=True
        ).start()


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/stats")
def stats() -> dict:
    """Quick look at how much data we've banked so far."""
    with SessionLocal() as s:
        by_source = dict(
            s.query(Battle.source, func.count()).group_by(Battle.source).all()
        )
        first, last = s.query(
            func.min(Battle.battle_time), func.max(Battle.battle_time)
        ).one()
        return {
            "battles": by_source,
            "players_in_frontier": s.query(PlayerSeen).count(),
            "first_battle": first,
            "last_battle": last,
        }


_cards_cache: dict | None = None


@app.get("/cards")
def cards() -> dict:
    """Card metadata for the dashboard: name -> {icon, rarity, elixir}.
    Fetched once from the official API per server process."""
    global _cards_cache
    if _cards_cache is None:
        from . import config
        from .clash_client import ClashClient

        items = ClashClient(config.API_TOKEN).cards()
        _cards_cache = {
            c["name"]: {
                "icon": (c.get("iconUrls") or {}).get("medium"),
                "rarity": c.get("rarity"),
                "elixir": c.get("elixirCost"),
            }
            for c in items
        }
    return _cards_cache


@app.get("/coach")
def coach() -> dict:
    """Personal coaching report: matchups, underleveled cards, tilt patterns."""
    with SessionLocal() as s:
        report = full_report(s)
    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])
    return report


# Guest reports are built from a live battle-log fetch; cache them briefly so
# a page refresh doesn't burn another upstream API call.
_guest_cache: dict[str, tuple[float, dict]] = {}
GUEST_CACHE_TTL = 120


@app.get("/coach/{tag}")
def coach_for_tag(tag: str) -> dict:
    """Scouting report for any player: fetches their recent battle log live
    and runs the same coach over it. Nothing is stored."""
    from . import config
    from .clash_client import ClashApiError, ClashClient, normalize_tag
    from .ingest.parse import battle_to_row
    from .ml.coach import build_report, is_competitive

    norm = normalize_tag(tag)
    cached = _guest_cache.get(norm)
    if cached and time.time() - cached[0] < GUEST_CACHE_TTL:
        return cached[1]

    try:
        log = ClashClient(config.API_TOKEN).battle_log(norm)
    except ClashApiError as e:
        raise HTTPException(404 if "404" in str(e) else 502, str(e))

    rows = [
        r
        for b in log
        if (r := battle_to_row(b, source="guest")) is not None and is_competitive(r)
    ]
    if not rows:
        raise HTTPException(
            404,
            f"No recent competitive 1v1 battles for {norm} — play a few "
            "ladder matches and try again.",
        )
    rows.sort(key=lambda r: r.battle_time)
    report = build_report(rows)
    report["player"] = {"tag": norm, "name": rows[-1].player_name}
    _guest_cache[norm] = (time.time(), report)
    return report


@app.get("/insights/global")
def global_insights(top: int = 20) -> dict:
    """Top SHAP features of the trained win model (what drives wins meta-wide).

    Served from a precomputed artifact — SHAP over the full battle bank takes
    minutes of CPU and hundreds of MB, which a small cloud instance can't
    absorb per-request (or even per-boot). See app.ml.export_insights.
    """
    import json

    from .ml.train import MODEL_DIR

    path = MODEL_DIR / "global_insights.json"
    if not path.exists():
        raise HTTPException(
            404, "No insights artifact — run `python -m app.ml.export_insights`."
        )
    data = json.loads(path.read_text())
    return {"n_battles": data["n_battles"], "top_features": data["top_features"][:top]}
