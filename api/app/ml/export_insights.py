"""Precompute the global SHAP insights into a static artifact.

    python -m app.ml.export_insights

SHAP over the full battle bank takes minutes of CPU and hundreds of MB on a
small cloud instance — enough to wedge or OOM it. The result only changes
when the model or data does, so compute it here at training time and ship
models/global_insights.json with the deploy; the API just reads the file.
Re-run after every `python -m app.ml.train`.
"""

import json

import joblib

from ..db import SessionLocal, init_db
from .explain import shap_values_for, top_features
from .features import battles_to_frame
from .train import MODEL_DIR

EXPORT_TOP_N = 50  # more than the API ever serves


def main() -> None:
    path = MODEL_DIR / "win_model.joblib"
    if not path.exists():
        raise SystemExit("No trained model — run `python -m app.ml.train` first.")
    # Safe: artifact is written locally by app.ml.train, never downloaded.
    bundle = joblib.load(path)
    init_db()
    with SessionLocal() as s:
        frame = battles_to_frame(s, source=bundle.get("source"))
    sv, X = shap_values_for(bundle, frame)
    out = {
        "n_battles": len(X),
        "top_features": top_features(sv, X, n=EXPORT_TOP_N),
    }
    dest = MODEL_DIR / "global_insights.json"
    dest.write_text(json.dumps(out, indent=2))
    print(f"wrote {dest} ({out['n_battles']} battles, {len(out['top_features'])} features)")


if __name__ == "__main__":
    main()
