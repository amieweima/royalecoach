# RoyaleCoach

An AI coach for Clash Royale. It banks your battle history through the official
Supercell API, trains a win-probability model on thousands of top-ladder
matches, and uses explainable ML (SHAP) to tell you *why* you win and lose —
matchup weaknesses, under-leveled cards, and tilt patterns a generic chatbot
can't see because they live in your personal data.

## How it works

```
Supercell API ──> ingestion (poller + top-ladder harvester) ──> SQLite/Postgres
                                                                    │
                     Next.js dashboard <── FastAPI <── ML models ───┘
                                                (win prediction, SHAP,
                                                 archetype clustering)
```

- **Poller** — the API only exposes your last ~25 battles, so a scheduled
  poller accumulates your personal history over time.
- **Harvester** — crawls top-ladder players' battle logs (rankings first, then
  outward through their opponents) to build a large global training set.
- **Models** *(in progress)* — gradient-boosted win prediction vs. naive
  baselines, unsupervised deck-archetype clustering, SHAP-based coaching
  insights, session/tilt analysis.

## Setup

Requirements: Python 3.12+, Node 18+ (dashboard).

```powershell
# 1. Python env
python -m venv .venv
.venv\Scripts\pip install -r api\requirements.txt

# 2. Credentials — copy .env.example to .env and fill in:
#    CLASH_API_TOKEN  from https://developer.clashroyale.com (key is IP-locked)
#    MY_PLAYER_TAG    from your in-game profile, e.g. #2PP8YQVL

# 3. Start collecting data (run from api/)
cd api
..\.venv\Scripts\python -m app.ingest.harvest --max-players 200   # global dataset
..\.venv\Scripts\python -m app.ingest.poller --loop               # your battles, keep running

# 4. Train the win model (needs ≥200 banked battles) and run tests
..\.venv\Scripts\python -m app.ml.train
..\.venv\Scripts\python -m pytest tests

# 5. API server
..\.venv\Scripts\python -m uvicorn app.main:app --reload
# then check http://localhost:8000/stats

# 6. Dashboard (separate terminal, from web/)
cd ..\web
npm install
npm run dev
# open http://localhost:3000
```

The database defaults to a local SQLite file; set `DATABASE_URL` in `.env` to
point at Postgres for a production deployment (SQLAlchemy makes this a
config-only change).

## Deploy

- **API + Postgres (Render):** the repo ships a `render.yaml` blueprint — in
  Render choose *New → Blueprint*, point it at this repo, then fill in
  `CLASH_API_TOKEN`, `MY_PLAYER_TAG`, and `ALLOWED_ORIGINS` (your dashboard
  URL). `ENABLE_POLLER=1` makes the API poll your battles in-process, so no
  separate worker is needed. Add the service's outbound IPs (shown in Render's
  service settings) to your key's allowed list at developer.clashroyale.com.
- **Dashboard (Vercel):** import the repo, set the root directory to `web/`,
  and add the env var `NEXT_PUBLIC_API_URL` pointing at the Render API URL.
- After the first deploy, seed the global dataset and models from Render's
  shell: `python -m app.ingest.harvest`, `python -m app.ml.train`,
  `python -m app.ml.archetypes`.

## Roadmap

- [x] Ingestion: personal poller + top-ladder harvester with crawl frontier
- [x] Feature engineering (deck multi-hot, card-level deltas, trophy diff,
      mirror-duplicate dedup) — `app/ml/features.py`, tested on synthetic data
- [x] Win-probability training pipeline + baseline comparison (base rate,
      trophies-only logistic regression vs. gradient boosting; time-based
      split; AUC/Brier/log-loss) — `python -m app.ml.train` once ≥200 battles
      are banked
- [x] Probability calibration (isotonic; calibrated Brier matches the base
      rate where the raw GBM was overconfident)
- [x] SHAP insights (`python -m app.ml.explain --plot`) + personal coaching
      report with matchups, underleveled cards, and tilt/session analysis
      (`python -m app.ml.coach`, served at `/coach` and `/insights/global`)
- [x] Next.js dashboard (`web/`) — scouting-report UI: auto-generated verdict
      headline, matchup + tilt + card-level charts, SHAP model insights
- [ ] Deck archetype clustering
- [ ] Deployment (Postgres + API on a host, dashboard on Vercel)
