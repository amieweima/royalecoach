"""Deck archetype clustering: learn the meta's deck families from harvested
battles, so matchup coaching can say "bait decks beat you" instead of the
popularity-confounded "The Log beats you" (The Log is in half the meta).

    python -m app.ml.archetypes         # fit clusters on harvested decks

Saves models/archetypes.joblib: KMeans centroids + card vocabulary + a
human-readable signature (most characteristic cards) per cluster.
"""

from functools import lru_cache

import joblib
import numpy as np
from sklearn.cluster import KMeans

from ..db import SessionLocal, init_db
from .features import battles_to_frame, card_vocabulary
from .train import MODEL_DIR

N_CLUSTERS = 10
SIGNATURE_CARDS = 4  # cards shown when naming an archetype

ARTIFACT = MODEL_DIR / "archetypes.joblib"


def _deck_matrix(decks: list[set[str]], vocab: list[str]) -> np.ndarray:
    index = {name: i for i, name in enumerate(vocab)}
    X = np.zeros((len(decks), len(vocab)), dtype=np.float32)
    for row, deck in enumerate(decks):
        for name in deck:
            col = index.get(name)
            if col is not None:
                X[row, col] = 1.0
    return X


def fit(n_clusters: int = N_CLUSTERS) -> dict:
    init_db()
    with SessionLocal() as session:
        frame = battles_to_frame(session, source="ladder")
    if len(frame) < 200:
        raise SystemExit(f"Only {len(frame)} battles banked — harvest more first.")

    vocab = card_vocabulary(frame)
    decks = [set(d) for col in ("p_cards", "o_cards") for d in frame[col]]
    X = _deck_matrix(decks, vocab)

    kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=0)
    labels = kmeans.fit_predict(X)

    # Name each archetype by the cards that most distinguish it from the meta
    # at large (highest lift over the global inclusion rate).
    global_rate = X.mean(axis=0)
    signatures: list[list[str]] = []
    for c in range(n_clusters):
        lift = kmeans.cluster_centers_[c] - global_rate
        top = np.argsort(lift)[::-1][:SIGNATURE_CARDS]
        signatures.append([vocab[i] for i in top])

    artifact = {
        "kmeans": kmeans,
        "vocab": vocab,
        "signatures": signatures,
        "sizes": np.bincount(labels, minlength=n_clusters).tolist(),
    }
    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(artifact, ARTIFACT)

    print(f"{len(decks)} decks -> {n_clusters} archetypes (saved to {ARTIFACT})\n")
    for c, sig in enumerate(signatures):
        print(f"  {artifact['sizes'][c]:>5} decks   {' · '.join(sig)}")
    return artifact


@lru_cache(maxsize=1)
def load() -> dict | None:
    if not ARTIFACT.exists():
        return None
    # Safe: artifact is written locally by fit() above, never downloaded.
    return joblib.load(ARTIFACT)


def classify(deck: set[str], artifact: dict) -> int:
    """Nearest-centroid archetype id for one deck."""
    X = _deck_matrix([deck], artifact["vocab"])
    return int(artifact["kmeans"].predict(X)[0])


if __name__ == "__main__":
    fit()
