"""Smoke test: the model must learn a planted signal and beat the base rate."""

import random

from conftest import DECK_A, DECK_B, deck_json, make_battle
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from app.ml.features import battles_to_frame, card_vocabulary, make_matrix

WIN_CARD_DECK = deck_json(["Win Card"] + DECK_A[:7])


def test_model_learns_planted_card_signal(session):
    rng = random.Random(42)
    battles = []
    for i in range(600):
        has_win_card = rng.random() < 0.5
        # The planted card wins 85% of the time; otherwise a coin flip.
        won = int(rng.random() < (0.85 if has_win_card else 0.5))
        battles.append(
            make_battle(
                i,
                won=won,
                p_deck=WIN_CARD_DECK if has_win_card else deck_json(DECK_A),
                o_deck=deck_json(DECK_B),
            )
        )
    session.add_all(battles)
    session.commit()

    frame = battles_to_frame(session).sort_values("battle_time").reset_index(drop=True)
    cut = int(len(frame) * 0.8)
    vocab = card_vocabulary(frame.iloc[:cut])
    X_train, y_train = make_matrix(frame.iloc[:cut], vocab)
    X_test, y_test = make_matrix(frame.iloc[cut:], vocab)

    model = HistGradientBoostingClassifier(max_iter=100)
    model.fit(X_train, y_train)
    auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    assert auc > 0.6, f"model failed to learn the planted signal (AUC={auc:.3f})"
