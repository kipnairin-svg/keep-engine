"""
Chubb Studio partner API adapter.

REAL, as of this writing: Chubb Studio is a live partner platform (relaunched
with AI-powered features in Nov 2025) exposing a RESTful API suite across the
policy lifecycle — products, pricing, distribution, servicing, claims. See
https://www.chubb.com/us-en/partners/technology.html.

NOT REAL YET: this codebase has no Chubb Studio partner account, so there is
no real base URL, client ID, or client secret to put in config.py, and this
adapter cannot make a live call. It runs in MOCK_MODE against
sample_data/chubb_sample_response.json until CHUBB_STUDIO_BASE_URL,
CHUBB_STUDIO_CLIENT_ID, and CHUBB_STUDIO_CLIENT_SECRET are set (see README
"Going live" section for what getting those actually requires — a partner
application, not just an email).

The OAuth2 client-credentials flow below is written to the pattern Chubb
Studio's own documentation describes (token endpoint, bearer auth on
subsequent calls) — it has not been tested against Chubb's real servers,
since this project doesn't have access to them.
"""

import json
import sys
from pathlib import Path

import requests

from . import base

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as cfg  # noqa: E402 (project-root import; see sys.path line above)

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "sample_data" / "chubb_sample_response.json"


class ChubbStudioAdapter(base.CarrierAdapter):
    carrier_name = "Chubb"
    source_tier = "direct_api"

    def __init__(self):
        self.base_url = cfg.CHUBB_STUDIO_BASE_URL
        self.client_id = cfg.CHUBB_STUDIO_CLIENT_ID
        self.client_secret = cfg.CHUBB_STUDIO_CLIENT_SECRET

    @property
    def mock_mode(self) -> bool:
        return not (self.base_url and self.client_id and self.client_secret)

    def authenticate(self) -> str:
        if self.mock_mode:
            return "MOCK_TOKEN_NO_REAL_CHUBB_CREDENTIALS"
        # Real OAuth2 client-credentials flow, per Chubb Studio partner docs.
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
            return data["policies"]
        resp = requests.get(
            f"{self.base_url}/v1/policies",
            headers={"Authorization": f"Bearer {token}"},
            params={"clientRef": client_ref},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["policies"]
