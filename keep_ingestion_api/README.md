# Keep Carrier Ingestion API

A real, running FastAPI service that ingests policy data from Chubb Studio,
PURE, and InsurGrid (aggregator), normalizes it into one schema, and answers
plain-language questions about it (`POST /ask` — "What is Chubb's auto
policy price?").

**What's real:** the code, the architecture, the OAuth2 client-credentials
auth flow, the normalization logic reconciling three genuinely different
carrier/aggregator data shapes, and the query engine's keyword parsing.
Everything runs and has been tested end to end, including a live
`uvicorn` server hit with real `curl` calls, not just `demo.py`.

**What's not real:** Keep has no Chubb Studio, PURE, or InsurGrid partner
account, so there are no real credentials and no real carrier data. All
three adapters run in `MOCK_MODE` against the sample files in
`sample_data/` until real credentials are supplied. Do not present this as
a live integration to anyone — it's the scaffold a real integration would
be built on top of, not a working connection to any of the three.

## Quick start

```bash
pip install -r requirements.txt

# No-server version — ingests all three mock sources and asks 7 questions:
python3 demo.py

# Or run it as an actual API:
uvicorn main:app --reload
```

With the server running:

```bash
curl -X POST http://127.0.0.1:8000/ingest/chubb
curl -X POST http://127.0.0.1:8000/ingest/pure
curl -X POST http://127.0.0.1:8000/ingest/insurgrid
curl http://127.0.0.1:8000/policies
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Chubb'"'"'s auto policy price?"}'
```

That last call returns:

```json
{"question": "What is Chubb's auto policy price?", "resolved": true,
 "answer": "$4,180/yr", "carrier": "Chubb", "line_of_business": "auto",
 "source_policy_id": "chubb-CHB-9931-AUTO", "source_tier": "direct_api", ...}
```

Ask about something not in the sample data (`"What is PURE's auto policy
price?"` — PURE's mock data only has umbrella and watercraft) and it
honestly reports it can't resolve the question, instead of guessing:

```json
{"question": "What is PURE's auto policy price?", "resolved": false,
 "message": "No ingested policy matches that yet. Either it hasn't been
 ingested, the carrier isn't connected, or the question doesn't include a
 recognizable carrier/line-of-business word...", ...}
```

Now ask about a carrier Keep has no direct relationship with at all —
Farmers, only reachable because InsurGrid was ingested:

```json
{"question": "What is Farmers' auto policy price?", "resolved": true,
 "answer": "$3,120/yr", "carrier": "Farmers", "line_of_business": "auto",
 "source_policy_id": "insurgrid-FARM-6602-AU", "source_tier": "aggregator", ...}
```

That's the actual point of the aggregator tier: it isn't a faster path to
Chubb/PURE, it's reach into carriers Keep has no adapter for at all.

## How the pieces fit together

```
adapters/chubb_studio.py   ──┐
adapters/pure_oneshield.py ──┤──> normalize.py ──> models.Policy ──> qa_engine.py ──> /ask
adapters/insurgrid.py      ──┘      (one shape,        (unified          (keyword
                                   regardless of        schema)          parsing +
                                     source)                              lookup)
sample_data/*.json  (mock data, used until real credentials exist)
```

- **`adapters/`** — one class per source, each implementing `authenticate()`
  and `fetch_policies()`. Chubb's, PURE's, and InsurGrid's raw sample data
  are deliberately structured differently (`policyNumber` vs `PolicyNum` vs
  `policy_number`; `premium.annualAmount` vs `AnnualPremiumAmt` vs
  `premium_total`; `coverages: [{coverageCode, limit}]` vs
  `CoverageSchedule: [{CovCode, CovLimit}]` vs `coverage_limits:
  [{label, amount}]`) — that's the real "every source is different"
  problem, reproduced on purpose rather than glossed over. InsurGrid's
  adapter is also structurally different from Chubb's/PURE's in one real
  way: `source_tier = "aggregator"`, and a single household connection can
  return multiple documents across multiple *underlying* carriers
  (Farmers, Travelers in the mock data) in one pull — carriers Keep has no
  direct adapter for at all. `models.Policy.carrier` always holds that
  underlying carrier, never "InsurGrid" itself; `aggregator_source` records
  InsurGrid separately. See the docstring in `adapters/insurgrid.py` for
  why its request/response shape is a best-guess scaffold (InsurGrid's real
  API schema isn't public) — same honesty pattern as `adapters/
  pure_oneshield.py`.
- **`normalize.py`** — the actual source-nuance-solving logic. One
  function per source maps its raw shape into the single `Policy` model
  in `models.py`. Adding a source means adding one adapter and one
  normalize function; nothing else changes.
- **`qa_engine.py`** — parses a question into (carrier, line of business,
  field) using the synonym lists in `config.py`, filters the ingested
  policies, and reads the real value off the matching `Policy` object.
  This is genuine parsing, not a lookup table of pre-written questions —
  reword a question and it still resolves, as long as the words involved
  are in `config.py`'s synonym lists. That's also the honest limit of what
  it can do: extend those lists as real usage turns up phrasing gaps. Note
  that `CARRIER_SYNONYMS` maps to actual carriers (Chubb, PURE, Farmers,
  Travelers, ...) — "InsurGrid" is deliberately not a matchable carrier
  keyword, since it's a data source, not a carrier a client holds a policy
  with.
- **`main.py`** — the FastAPI app wiring the above into HTTP endpoints:
  `/ingest/chubb`, `/ingest/pure`, `/ingest/insurgrid`, `/policies`, `/ask`.
- **`demo.py`** — the same logic without needing a server running, for a
  fast sanity check.

## Going live with Chubb Studio

Chubb Studio is a real, current partner API platform (relaunched with
AI-powered features in Nov 2025) exposing a RESTful suite across the full
policy lifecycle, including servicing — see
[chubb.com/us-en/partners/technology.html](https://www.chubb.com/us-en/partners/technology.html).
It's built primarily for embedded-distribution partners (selling Chubb's
product inside a partner's own channel), so pulling existing clients'
declarations data for a third-party advisory platform is a custom
conversation with their partnerships team, not a self-serve signup. Once
that conversation produces a real base URL, client ID, and client secret,
set them as environment variables:

```bash
export CHUBB_STUDIO_BASE_URL="https://<real-partner-base-url>"
export CHUBB_STUDIO_CLIENT_ID="<real-client-id>"
export CHUBB_STUDIO_CLIENT_SECRET="<real-client-secret>"
```

`adapters/chubb_studio.py` will automatically leave mock mode and start
making real HTTP calls once all three are set — nothing else in the
codebase needs to change. The OAuth2 client-credentials flow it uses is
written to match Chubb's own documented pattern, but has not been tested
against Chubb's real servers, since this project doesn't have access to
them yet. Confirm the actual token/policy endpoint paths against their
real partner docs before flipping this on.

## Going live with PURE

PURE is different: it runs on OneShield (a 20+ year platform partnership)
and services agents through an agent portal, not an open public developer
API — see
[oneshield.com/clients/privilege-underwriters-reciprocal-exchange-pure](https://oneshield.com/clients/privilege-underwriters-reciprocal-exchange-pure/).
The realistic path to PURE policy data is becoming an appointed PURE
producer and pulling through that agent portal, or negotiating a direct
OneShield data-sharing agreement — not a signup form. `adapters/
pure_oneshield.py` is written as a best-guess scaffold for what that
integration might look like technically; the actual mechanism (a REST API,
an SFTP export, something else) has not been confirmed with PURE and
should be treated as unknown until a real integration contact says
otherwise. Same environment-variable pattern once it is:

```bash
export PURE_ONESHIELD_BASE_URL="https://<real-base-url>"
export PURE_ONESHIELD_CLIENT_ID="<real-client-id>"
export PURE_ONESHIELD_CLIENT_SECRET="<real-client-secret>"
```

## Going live with InsurGrid

InsurGrid (insurgrid.com) is a real, currently-operating aggregator — a
direct competitor to Canopy Connect — with 450+ carrier connections, AI
dec-page extraction across Auto/Home/Umbrella/Workers Comp/Cyber/Flood/GL,
its own API/webhooks, roughly 2,500 agents on it already, and (per a
third-party agency-tech comparison, not InsurGrid's own pricing page) a
$99/mo unlimited-pull agent plan. This is the path that reaches carriers
Keep will never get a direct API for — Farmers and Travelers in this repo's
mock data are stand-ins for that exact case.

The consent mechanic is the part worth internalizing before pitching this,
not just the code: Keep signs up once as InsurGrid's business/API customer;
each household then authenticates with **their own** carrier login through
InsurGrid's embedded widget — that's the actual moment of consent, and Keep
never sees or stores that carrier password. This grants read-only
visibility into that household's policies, never authority to bind or
change coverage. If a household doesn't remember their carrier login,
that's a real gap this tier doesn't solve by itself (they'd need to reset
it with the carrier first) — not something to paper over.

`adapters/insurgrid.py` is a best-guess scaffold, the same honesty caveat
as the PURE adapter: InsurGrid's actual request/response schema is not
public, so the connection/document shape it's written against
(`sample_data/insurgrid_sample_response.json`) is inferred from InsurGrid's
own marketing copy about what it extracts, not from real API docs. Confirm
the real schema and endpoint paths with an InsurGrid integration contact
before flipping this on. Same environment-variable pattern once that
happens:

```bash
export INSURGRID_BASE_URL="https://<real-base-url>"
export INSURGRID_CLIENT_ID="<real-client-id>"
export INSURGRID_CLIENT_SECRET="<real-client-secret>"
```

Cheapest real next step, before any of this: ask InsurGrid's (and Canopy
Connect's) sales teams directly whether a pre-revenue, pre-licensed startup
is even eligible to sign up today — that answer determines whether this
adapter is weeks away from going live or blocked on Keep's own licensing
status first.

## Before any real household's data goes through this

This is a prototype. Before it touches a real person's real policy data:
storage needs to move off an in-memory Python list (no persistence, no
encryption, wiped on restart) and onto a real database with encryption at
rest; the OAuth token handling needs a proper secrets manager instead of
plain environment variables; and — separately from the engineering — Keep
needs to actually be the appropriate legal party to hold this data (licensed
producer status, a signed carrier agreement, and a data-handling review),
which is a business and compliance step, not a code change.

## Files

- `main.py` — FastAPI app: `/ingest/chubb`, `/ingest/pure`, `/ingest/insurgrid`, `/policies`, `/ask`
- `demo.py` — same logic, no server required
- `models.py` — the normalized `Policy` schema everything maps into
- `normalize.py` — source-specific raw-shape → `Policy` mapping
- `qa_engine.py` — plain-language question parsing and lookup
- `config.py` — credential env-var wiring + the synonym lists `qa_engine.py` uses
- `adapters/chubb_studio.py`, `adapters/pure_oneshield.py`, `adapters/insurgrid.py` — one per source (direct_api, direct_api, aggregator)
- `sample_data/` — the mock responses used in `MOCK_MODE`
