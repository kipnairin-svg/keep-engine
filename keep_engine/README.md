# Keep Engine

The "Engine" from Keep's own Inputs → Engine → Outputs framing, actually
running. Sits on top of `../keep_ingestion_api` (Inputs: Chubb, PURE,
InsurGrid) rather than duplicating it, and adds the three things that
project deliberately left out: a place to persist a household's ingested
policies, real gap-detection logic run against them, and the three actual
product outputs (Gap Alerts / Advisor Action Plan / Household
Notification) generated from real findings instead of written by hand.

**What's real:** every rule in `gap_rules.py` traces back to reasoning
already done manually, in chat, against two real households this session —
Kip's own policies, and the Nairin household. This file turns that same
reasoning into code that reruns it, rather than a set of one-off writeups.
The API, the SQLite persistence, and the report generation all run and
have been tested end to end, including a live `uvicorn` server hit with
real `curl` calls.

**What's not real:** the carrier data underneath it (see
`../keep_ingestion_api/README.md` — still mock-mode, no real Chubb/PURE/
InsurGrid credentials). And several rules are written to say "we don't
know yet" instead of guessing, on purpose — see `R3_jewelry_data_gap` and
`R4_valuation_staleness_gap` below. That's not a placeholder to be
embarrassed about; it's the same honesty discipline as everything else
built this session, now enforced in code instead of by hand each time.

## Quick start

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

```bash
curl -X POST http://127.0.0.1:8001/households \
  -H "Content-Type: application/json" \
  -d '{"name": "Whitfield Household", "state": "UT"}'

curl -X POST http://127.0.0.1:8001/households/1/ingest/chubb
curl -X POST http://127.0.0.1:8001/households/1/ingest/pure
curl -X POST http://127.0.0.1:8001/households/1/ingest/insurgrid

curl http://127.0.0.1:8001/households/1/gaps

# Open in a browser:
http://127.0.0.1:8001/households/1/report   # the full 3-part output
http://127.0.0.1:8001/dashboard              # every household at a glance
```

If SQLite raises a "disk I/O error" (only seen on networked/mounted
filesystems, not a normal local machine), point it at local disk instead:

```bash
KEEP_ENGINE_DB_PATH=/tmp/keep_engine.db uvicorn main:app --reload --port 8001
```

## The six rules in `gap_rules.py`, honestly described

- **R1 — No umbrella on file.** Fires only if $1M+ in dwelling + personal
  property is ingested with zero umbrella policy. High severity, but
  phrased as "confirm," not "you're exposed" — could just mean the
  umbrella hasn't been connected yet, not that one doesn't exist.
- **R2 — Umbrella sized too small.** Fires when total insured property
  value is more than 2x the umbrella limit. This is the rule from Kip's
  and the Nairin household's manual reviews, generalized.
- **R3 — Jewelry/valuables.** If a homeowners policy's ingested data
  actually contains a jewelry/valuables sub-limit under $5,000, flags it as
  low. If that data point simply isn't there — the common case, since most
  dec-page summaries don't itemize it — flags the **data gap itself**
  instead of assuming a number. This is deliberate: guessing an exposure
  figure with no basis would be exactly the kind of overclaim this project
  has been built to avoid.
- **R4 — Valuation staleness.** This is Kip's own insight from the pilot
  runs — every insured value could be years stale, and it's a universal
  risk, not just a jewelry one. Currently always fires as an honest
  limitation notice (no adapter captures a "last valued" date yet) rather
  than a fabricated drift percentage. Once a real last-valuation-date field
  exists in the ingested data, this is the rule to upgrade into an actual
  computed number.
- **R5 — Earthquake exclusion.** Always flagged for any homeowners policy;
  bumped to medium severity in states with real seismic exposure
  (`HIGH_SEISMIC_STATES` in `gap_rules.py` — extend as needed).
- **R6 — Flood exclusion.** Always flagged; standard on every homeowners
  policy, not carrier-specific, so it always fires when a homeowners policy
  exists.

## How the pieces fit together

```
../keep_ingestion_api/adapters/*  ──> normalize.py ──> Policy objects
                                                            │
                                                            ▼
                                          db.py  (SQLite: households, policies, gap_findings)
                                                            │
                                                            ▼
                                          gap_rules.py  (the six rules above)
                                                            │
                                                            ▼
                                          reports.py  (Gap Alerts / Action Plan / Notification, one HTML page)
                                                            │
                                                            ▼
                                          main.py  (FastAPI: /households, /ingest, /gaps, /report, /dashboard)
```

- **`db.py`** — three SQLite tables. Policies are stored as the exact JSON
  a `Policy` object serializes to, so nothing is lost in translation
  between ingestion and gap detection.
- **`gap_rules.py`** — `evaluate(policies, household_state)` → list of
  finding dicts. Pure function, no I/O, easy to test or extend with new
  rules independent of the API layer.
- **`reports.py`** — turns a household + its findings into the same
  three-part HTML report structure already validated in
  `Keep_Engine_Output_Nairin.html` earlier this session, now generated from
  real findings instead of hand-written per household.
- **`main.py`** — wires it into HTTP endpoints and a plain dashboard.

## Before this holds a real household's data

Same list as `../keep_ingestion_api/README.md`, plus one more: this is
single-user, unencrypted local SQLite. Fine for Kip running pilots on his
own machine. Not fine for a second person's data at rest, or for anything
beyond this grassroots pilot phase — that needs a hosted, encrypted,
access-controlled database before it's a real product, separate from and
in addition to the licensing/carrier-agreement work already flagged
upstream.

## Files

- `main.py` — FastAPI app: household CRUD, ingestion, `/gaps`, `/report`, `/dashboard`
- `db.py` — SQLite persistence (households, policies, gap_findings)
- `gap_rules.py` — the six gap-detection rules, pure function
- `reports.py` — the three-part HTML report generator
- `requirements.txt` — fastapi, uvicorn, pydantic, requests (same as `../keep_ingestion_api`)
