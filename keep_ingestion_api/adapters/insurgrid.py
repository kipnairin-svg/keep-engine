"""
InsurGrid adapter — the aggregator tier, not a direct carrier relationship.

REAL, as of this writing: InsurGrid (insurgrid.com) is a live, direct
competitor to Canopy Connect — 450+ carrier connections, AI dec-page
extraction across Auto/Home/Umbrella/Workers Comp/Cyber/Flood/GL, its own
API/webhooks, ~2,500 agents already on it, SF-based. See insurgrid.com and
third-party agency-tech comparisons for the $99/mo unlimited-pull agent
plan. Unlike Chubb Studio or PURE, InsurGrid is not itself a carrier — it's
the pipe that reaches carriers Keep has no direct relationship with at all
(this mock data uses Farmers and Travelers on purpose, to make that point:
neither has a Keep adapter of its own).

NOT REAL YET: this codebase has no InsurGrid partner/API account, so there
is no real base URL, client ID, or client secret to put in config.py.
InsurGrid's actual request/response schema is also not public — the
connection/document shape below (sample_data/insurgrid_sample_response.json)
is a best-guess scaffold built from InsurGrid's own marketing copy about
what it extracts, the same way adapters/pure_oneshield.py is a best-guess
scaffold for PURE. Treat both the endpoint paths and the JSON shape here as
placeholders to replace once a real InsurGrid integration contact confirms
the actual API.

The client-consent mechanic this adapter assumes (and the reason
`client_ref` matters here more than for Chubb/PURE): each household
authenticates with THEIR OWN carrier login through InsurGrid's embedded
widget — Keep never sees or stores that carrier password. This adapter
models the step *after* that consent moment: pulling back what InsurGrid
already extracted for a given household/connection.

Runs in MOCK_MODE against sample_data/insurgrid_sample_response.json until
INSURGRID_BASE_URL, INSURGRID_CLIENT_ID, and INSURGRID_CLIENT_SECRET are set.
"""

import json
import sys
from pathlib import Path

import requests

from . import base

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as cfg  # noqa: E402 (project-root import; see sys.path line above)

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "sample_data" / "insurgrid_sample_response.json"


class InsurGridAdapter(base.CarrierAdapter):
    carrier_name = "InsurGrid"
    source_tier = "aggregator"

    def __init__(self):
        self.base_url = cfg.INSURGRID_BASE_URL
        self.client_id = cfg.INSURGRID_CLIENT_ID
        self.client_secret = cfg.INSURGRID_CLIENT_SECRET

    @property
    def mock_mode(self) -> bool:
        return not (self.base_url and self.client_id and self.client_secret)

    def authenticate(self) -> str:
        if self.mock_mode:
            return "MOCK_TOKEN_NO_REAL_INSURGRID_CREDENTIALS"
        # Written to the generic OAuth2 client-credentials shape most
        # partner APIs in this space use — NOT confirmed against InsurGrid's
        # real docs, since this project has no partner account yet.
        resp = requests.post(
            f"{self.base_url}/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def fetch_policies(self, client_ref: str) -> list[dict]:
        token = self.authenticate()
        if self.mock_mode:
            data = json.loads(SAMPLE_PATH.read_text())
            return data["documents"]
        # One InsurGrid connection can return multiple documents across
        # multiple carriers/LOBs for a single household — unlike Chubb/PURE,
        # this is a one-to-many pull per client_ref, not one-to-one.
        resp = requests.get(
            f"{self.base_url}/v1/connections/{client_ref}/documents",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["documents"]
