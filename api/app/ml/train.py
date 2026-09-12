"""Train the win-probability model and compare it against honest baselines.

    python -m app.ml.train                 # all banked battles
    python -m app.ml.train --source ladder # harvested global data only
    python -m app.ml.train --source me     # personal battles only

Uses a time-based split (train on the past, test on the future) so the
reported metrics reflect real forecasting, not interpolation. Saves the
fitted model + card vocabulary to api/models/win_model.joblib.
"""

import argparse
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score

from ..db import SessionLocal, init_db
from .features import battles_to_frame, card_vocabulary, make_matrix

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
TEST_FRACTION = 0.2


def evaluate(name: str, y_true, y_prob) -> dict:
    y_pred = (np.asarray(y_prob) >= 0.5).astype(int)
    metrics = {
        "model": name,
        "auc": roc_auc_score(y_true, y_prob),
        "accuracy": accuracy_score(y_true, y_pred),
        "brier": brier_score_loss(y_true, y_prob),
        "log_loss": log_loss(y_true, y_prob, labels=[0, 1]),
    }
    print(
        f"{name:<24} AUC {metrics['auc']:.3f}  "
        f"acc {metrics['accuracy']:.3f}  "
        f"brier {metrics['brier']:.3f}  "
        f"logloss {metrics['log_loss']:.3f}"
    )
    return metrics


def train(source: str | None = None, save: bool = True) -> dict:
    init_db()
    with SessionLocal() as session:
        frame = battles_to_frame(session, source=source)

    if len(frame) < 200:
        raise SystemExit(
            f"Only {len(frame)} usable battles banked — run the harvester/poller "
            "longer before training (need at least 200)."
        )

    # Time-based split: past → train, future → test.
    frame = frame.sort_values("battle_time").reset_index(drop=True)
    cut = int(len(frame) * (1 - TEST_FRACTION))
    train_frame, test_frame = frame.iloc[:cut], frame.iloc[cut:]

    vocab = card_vocabulary(train_frame)  # vocab from train only — no peeking
    X_train, y_train = make_matrix(train_frame, vocab)
    X_test, y_test = make_matrix(test_frame, vocab)
    print(
        f"{len(frame)} battles ({len(train_frame)} train / {len(test_frame)} test), "
        f"{X_train.shape[1]} features, {len(vocab)} cards in vocabulary\n"
    )

    results = []

    # Baseline 1: predict the training-set base rate for everyone.
    base_rate = y_train.mean()
    results.append(
        evaluate("baseline: base rate", y_test, np.full(len(y_test), base_rate))
    )

    # Baseline 2: trophy difference alone.
    lr = LogisticRegression()
    lr.fit(X_train[["trophy_diff"]], y_train)
    results.append(
        evaluate(
            "baseline: trophies only",
            y_test,
            lr.predict_proba(X_test[["trophy_diff"]])[:, 1],
        )
    )

    # The real model: gradient boosting over decks, levels, and trophies.
    gbm = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05)
    gbm.fit(X_train, y_train)
    results.append(
        evaluate("gradient boosting", y_test, gbm.predict_proba(X_test)[:, 1])
    )

    # Same model with calibrated probabilities — a coach that says "62% win
    # chance" must mean it, so Brier/log-loss are the metrics to watch here.
    calibrated = CalibratedClassifierCV(
        HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05),
        method="isotonic",
        cv=3,
    )
    calibrated.fit(X_train, y_train)
    results.append(
        evaluate("gbm + calibration", y_test, calibrated.predict_proba(X_test)[:, 1])
    )

    if save:
        MODEL_DIR.mkdir(exist_ok=True)
        path = MODEL_DIR / "win_model.joblib"
        # `model` (calibrated) is what predictions should use; `gbm` is kept
        # for SHAP, which needs the raw tree model.
        joblib.dump(
            {"model": calibrated, "gbm": gbm, "vocab": vocab, "source": source}, path
        )
        print(f"\nSaved model to {path}")

    return {"n_battles": len(frame), "results": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["me", "ladder"], default=None)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()
    train(source=args.source, save=not args.no_save)


if __name__ == "__main__":
    main()
