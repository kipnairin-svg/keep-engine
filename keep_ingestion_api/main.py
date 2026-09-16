"""
Keep Carrier Ingestion API — FastAPI entry point.

Run it:
    pip install -r requirements.txt
    uvicorn main:app --reload

Then:
    curl -X POST http://127.0.0.1:8000/ingest/chubb
    curl -X POST http://127.0.0.1:8000/ingest/pure
    curl -X POST http://127.0.0.1:8000/ingest/insurgrid
    curl http://127.0.0.1:8000/policies
    curl -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" \
         -d '{"question": "What is Chubb'"'"'s auto policy price?"}'

Runs entirely in MOCK_MODE (against sample_data/) until real Chubb Studio,
PURE, and/or InsurGrid credentials are set as environment variables — see
README.md. The policy store here is a plain in-memory list, reset every
time the server restarts; swapping in a real database is the obvious next
step before this goes near a real household's data.
"""

from fastapi import FastAPI
from pydantic import BaseModel

import normalize
import qa_engine
from adapters.chubb_studio import ChubbStudioAdapter
from adapters.insurgrid import InsurGridAdapter
from adapters.pure_oneshield import PureOneShieldAdapter
from models import Policy

app = FastAPI(
    title="Keep Carrier Ingestion API",
    description="Ingests policy data from Chubb Studio, PURE, and InsurGrid (aggregator), normalizes it, and answers plain-language questions about it.",
    version="0.1.0",
)

POLICY_STORE: list[Policy] = []


@app.post("/ingest/chubb")
def ingest_chubb(client_ref: str = "demo-household-01"):
    adapter = ChubbStudioAdapter()
    raw_policies = adapter.fetch_policies(client_ref)
    normalized = [normalize.normalize_chubb(r) for r in raw_policies]
    POLICY_STORE.extend(normalized)
    return {
        "carrier": "Chubb",
        "mock_mode": adapter.mock_mode,
        "ingested_count": len(normalized),
        "policy_ids": [p.policy_id for p in normalized],
    }


@app.post("/ingest/pure")
def ingest_pure(client_ref: str = "demo-household-01"):
    adapter = PureOneShieldAdapter()
    raw_policies = adapter.fetch_policies(client_ref)
    normalized = [normalize.normalize_pure(r) for r in raw_policies]
    POLICY_STORE.extend(normalized)
    return {
        "carrier": "PURE",
        "mock_mode": adapter.mock_mode,
        "ingested_count": len(normalized),
        "policy_ids": [p.policy_id for p in normalized],
    }


@app.post("/ingest/insurgrid")
def ingest_insurgrid(client_ref: str = "demo-household-01"):
    adapter = InsurGridAdapter()
    raw_documents = adapter.fetch_policies(client_ref)
    normalized = [normalize.normalize_insurgrid(r) for r in raw_documents]
    POLICY_STORE.extend(normalized)
    return {
        "carrier": "InsurGrid (aggregator)",
        "mock_mode": adapter.mock_mode,
        "ingested_count": len(normalized),
        "policy_ids": [p.policy_id for p in normalized],
        "underlying_carriers": sorted({p.carrier for p in normalized}),
    }


@app.get("/policies")
def list_policies():
    return POLICY_STORE


class AskRequest(BaseModel):
    question: str


@app.post("/ask")
def ask(req: AskRequest):
    return qa_engine.answer(req.question, POLICY_STORE)


@app.get("/")
def root():
    return {
        "service": "Keep Carrier Ingestion API",
        "status": "mock_mode — no real Chubb/PURE/InsurGrid credentials configured",
        "endpoints": ["/ingest/chubb", "/ingest/pure", "/ingest/insurgrid", "/policies", "/ask"],
    }
