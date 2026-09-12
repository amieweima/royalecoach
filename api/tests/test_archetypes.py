from conftest import DECK_A, DECK_B
from sklearn.cluster import KMeans

from app.ml.archetypes import _deck_matrix, classify


def test_classify_separates_deck_families():
    vocab = sorted(set(DECK_A + DECK_B))
    decks = [set(DECK_A)] * 20 + [set(DECK_B)] * 20
    X = _deck_matrix(decks, vocab)
    artifact = {
        "kmeans": KMeans(n_clusters=2, n_init=5, random_state=0).fit(X),
        "vocab": vocab,
    }

    a = classify(set(DECK_A), artifact)
    b = classify(set(DECK_B), artifact)
    assert a != b

    # a one-card variant still lands with its family
    variant = set(DECK_A[:7]) | {"Rocket"}
    assert classify(variant, artifact) == a


def test_matrix_ignores_unknown_cards():
    vocab = sorted(set(DECK_A))
    X = _deck_matrix([{"Not A Real Card"} | set(DECK_A)], vocab)
    assert X.sum() == len(DECK_A)
