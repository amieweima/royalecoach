"""SHAP explanations for the win model: which features actually drive wins.

    python -m app.ml.explain                  # top features, printed
    python -m app.ml.explain --plot           # also save a beeswarm PNG

Uses the raw gradient-boosting model from the saved bundle (TreeExplainer
needs trees, not the calibration wrapper).
"""

import argparse
from pathlib import Path

import joblib
import numpy as np
import shap

from ..db import SessionLocal, init_db
from .features import battles_to_frame, make_matrix
from .train import MODEL_DIR

REPORT_DIR = Path(__file__).resolve().parents[2] / "reports"
MAX_SAMPLE = 2000  # SHAP cost grows with rows; a sample is plenty for trends


def shap_values_for(bundle: dict, frame) -> tuple:
    """Return (shap_values, X) for a sample of battles."""
    if len(frame) > MAX_SAMPLE:
        frame = frame.sample(MAX_SAMPLE, random_state=0)
    X, _ = make_matrix(frame, bundle["vocab"])
    explainer = shap.TreeExplainer(bundle["gbm"])
    return explainer.shap_values(X), X


def top_features(shap_values, X, n: int = 20) -> list[dict]:
    """Features ranked by mean |SHAP|, with the direction they push."""
    mean_abs = np.abs(shap_values).mean(axis=0)
    order = np.argsort(mean_abs)[::-1][:n]
    out = []
    for i in order:
        col = X.columns[i]
        # For binary card columns, direction = effect when the card is present.
        mask = X[col] == 1 if set(X[col].unique()) <= {0, 1} else X[col] > X[col].median()
        direction = shap_values[mask.to_numpy(), i].mean() if mask.any() else 0.0
        out.append(
            {
                "feature": col,
                "importance": float(mean_abs[i]),
                "direction": "wins" if direction > 0 else "losses",
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["me", "ladder"], default=None)
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    path = MODEL_DIR / "win_model.joblib"
    if not path.exists():
        raise SystemExit("No saved model — run `python -m app.ml.train` first.")
    # Safe: this artifact is produced locally by our own app.ml.train, never
    # downloaded. Don't point this at model files from untrusted sources.
    bundle = joblib.load(path)

    init_db()
    with SessionLocal() as session:
        frame = battles_to_frame(session, source=args.source or bundle.get("source"))

    sv, X = shap_values_for(bundle, frame)
    print(f"SHAP over {len(X)} battles, {X.shape[1]} features\n")
    print(f"{'feature':<40} {'mean |SHAP|':>12}   pushes toward")
    for f in top_features(sv, X, n=args.top):
        print(f"{f['feature']:<40} {f['importance']:>12.4f}   {f['direction']}")

    if args.plot:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        REPORT_DIR.mkdir(exist_ok=True)
        shap.summary_plot(sv, X, max_display=25, show=False)
        out = REPORT_DIR / "shap_summary.png"
        plt.gcf().set_size_inches(10, 8)
        plt.savefig(out, bbox_inches="tight", dpi=150)
        print(f"\nSaved beeswarm plot to {out}")


if __name__ == "__main__":
    main()
