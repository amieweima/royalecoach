import os
import time
from urllib.parse import quote

import httpx

# Cloud hosts (e.g. Render) have unpredictable outbound IPs, which the official
# API's per-key IP allowlist can't express. Point CLASH_API_BASE at the
# RoyaleAPI proxy (https://proxy.royaleapi.dev/v1) there and allowlist its
# single static IP (45.79.218.79) on the key instead.
BASE = os.getenv("CLASH_API_BASE", "https://api.clashroyale.com/v1")


class ClashApiError(RuntimeError):
    pass


def normalize_tag(tag: str) -> str:
    """Clean up a player tag as typed by a human: trim, uppercase, add the
    leading #, and swap letter O for zero (tags never contain O, but players
    read 0 as O all the time)."""
    return "#" + tag.strip().lstrip("#").upper().replace("O", "0")


class ClashClient:
    """Thin wrapper over the official Clash Royale API with throttling and
    friendly error messages."""

    def __init__(self, token: str, min_interval: float = 0.6):
        if not token or token.startswith("paste-"):
            raise ClashApiError(
                "CLASH_API_TOKEN is not set. Copy .env.example to .env and paste "
                "your key from https://developer.clashroyale.com"
            )
        self._client = httpx.Client(
            base_url=BASE,
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        self._min_interval = min_interval
        self._last_request = 0.0

    def _get(self, path: str, params: dict | None = None) -> dict:
        # simple throttle to stay well under rate limits
        wait = self._min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        resp = self._client.get(path, params=params)
        self._last_request = time.monotonic()

        if resp.status_code == 403:
            raise ClashApiError(
                "403 from the API: your key is invalid OR your current IP is not "
                "on the key's allowed list. Edit the key at developer.clashroyale.com."
            )
        if resp.status_code == 404:
            raise ClashApiError(f"404: not found ({path}) — check the player tag.")
        if resp.status_code == 429:
            time.sleep(10)
            resp = self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    def player(self, tag: str) -> dict:
        return self._get(f"/players/{quote(tag)}")

    def cards(self) -> list[dict]:
        """All cards in the game, with official icon URLs and rarities."""
        return self._get("/cards").get("items", [])

    def battle_log(self, tag: str) -> list[dict]:
        return self._get(f"/players/{quote(tag)}/battlelog")

    def top_players(self, limit: int = 100) -> list[dict]:
        """Top of the global ladder. Prefers Path of Legends rankings, falls
        back to the legacy trophy rankings if that endpoint is unavailable."""
        try:
            data = self._get(
                "/locations/global/pathoflegend/players", params={"limit": limit}
            )
        except (ClashApiError, httpx.HTTPStatusError):
            data = self._get(
                "/locations/global/rankings/players", params={"limit": limit}
            )
        return data.get("items", [])
