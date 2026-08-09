# Day 24 — Funnel Drop-off Analyzer

Day 24 of a daily AI-app series (BI focus). A conversion-funnel analytics
engine: it takes user-level event logs, computes stage-to-stage conversion
for a multi-step funnel, statistically tests whether specific segments
(acquisition channel, device) underperform, measures how long users take
to move between stages, and generates a plain-English executive narrative
with concrete recommendations — all served behind a Flask API and a live
dashboard, with SQLite history so you can track conversion trend over time.

**Complexity tier:** multi-component app with persistent storage, a
statistics layer (two-proportion z-tests via `scipy`), templated NLG, a
REST API, a Chart.js dashboard, and a test suite.

## Why this matters for BI work

Funnel analysis is one of the most common asks in product/growth BI:
"where are we losing users, and is it worse for a specific channel or
device?" Doing this well requires more than a bar chart — you need to
know whether an apparent segment gap is real (statistically significant)
or just noise, and you need a runnable audit trail so the finding is
reproducible and trend-able, not a one-off spreadsheet.

## Architecture

```
day24-funnel-dropoff-analyzer/
├── src/
│   ├── data_gen.py   # synthetic event-log generator (visit→signup→activate→purchase→retain)
│   ├── funnel.py      # FunnelAnalyzer: stage counts, drop-off, segment z-tests, time-to-convert
│   ├── narrative.py   # template-based NLG: summary + recommendations from the report
│   ├── storage.py     # SQLite snapshot persistence + trend-vs-previous
│   └── app.py          # Flask REST API + dashboard route
├── templates/
│   └── dashboard.html  # Chart.js funnel bar chart, narrative panel, segment table
├── tests/
│   ├── test_funnel.py  # funnel math + significance-flagging correctness
│   └── test_storage.py # SQLite round-trip + trend calculation
├── data/
│   └── events.csv       # small committed sample dataset (regenerate a larger one anytime)
├── run_demo.py           # CLI: generate data → analyze → persist → print narrative
└── requirements.txt
```

**Pipeline:** `data_gen` produces per-user event rows with a channel and
device attached → `funnel.py` reshapes events into a user × stage
"first reached" matrix, computes overall and per-segment conversion, runs
a two-proportion z-test comparing each segment against the rest of the
population at every stage transition, and finds the single steepest
drop-off → `narrative.py` turns that structured report into readable text
→ `storage.py` persists a timestamped snapshot to SQLite so later runs can
report a trend → `app.py` exposes all of this over HTTP and renders it in
`dashboard.html`.

## Running it

```bash
pip install -r requirements.txt

# 1. CLI demo (generates data/events.csv if missing, prints funnel + narrative)
python run_demo.py
python run_demo.py --regenerate --n-users 8000   # force a fresh synthetic dataset

# 2. Web dashboard + API
python -m src.app
# open http://localhost:5024

# 3. Tests
pytest tests/ -v
```

### API endpoints

| Endpoint | Description |
|---|---|
| `GET /api/funnel` | Recompute the funnel from `data/events.csv`, persist a snapshot, return full JSON report + narrative |
| `GET /api/funnel/latest` | Return the most recently persisted snapshot without recomputing |
| `GET /api/funnel/history` | List past snapshots (id, timestamp, overall conversion %) |
| `GET /api/funnel/trend` | Latest vs. previous snapshot conversion delta |
| `GET /` | Dashboard UI |

## Notes on the synthetic data

`src/data_gen.py` simulates 6,000 users across 4 acquisition channels and
2 devices with deliberately uneven conversion rates (paid traffic
converts worse than organic/referral; mobile underperforms desktop
specifically at the purchase step) so the analyzer has genuine,
statistically detectable patterns to surface — not just random noise.
