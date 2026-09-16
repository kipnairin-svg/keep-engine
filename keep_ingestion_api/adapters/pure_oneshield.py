"""
PURE (Privilege Underwriters Reciprocal Exchange) adapter.

REAL, as of this writing: PURE runs its policy administration on OneShield
(a 20+ year partnership) and services agents through an agent portal with
integrations like Auto Pre-Fill (via LexisNexis) and Agent Endorsement. See
https://oneshield.com/clients/privilege-underwriters-reciprocal-exchange-pure/.

IMPORTANT DIFFERENCE FROM CHUBB: PURE does not expose an open public
developer API the way Chubb Studio does. The realistic path to policy data
here is becoming an appointed PURE producer and pulling through the
OneShield-backed agent portal, or a negotiated data-sharing agreement — not
a self-serve API signup. This adapter is written as if a servicing
API/export endpoint exists, because that is the most plausible shape a
future integration would take, but that endpoint is NOT documented publicly
and has not been confirmed with PURE. Treat this file as a best-guess
scaffold to swap real logic into once an actual PURE/OneShield integration
contact confirms the real mechanism (API, SFTP export, portal-scrape-via-
authorized-tool, etc.).

Runs in MOCK_MODE against sample_data/pure_sample_response.json until
PURE_ONESHIELD_BASE_URL, PURE_ONESHIELD_CLIENT_ID, and
PURE_ONESHIELD_CLIENT_SECRET are set.
"""

import json
import sys
from pathlib import Path

import requests

from . import base

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as cfg  # noqa: E402 (project-root import; see sys.path line above)

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "sample_data" / "pure_sample_response.json"


class PureOneShieldAdapter(base.CarrierAdapter):
    carrier_name = "PURE"
    source_tier = "direct_api"

    def __init__(self):
        self.base_url = cfg.PURE_ONESHIELD_BASE_URL
        self.client_id = cfg.PURE_ONESHIELD_CLIENT_ID
        self.client_secret = cfg.PURE_ONESHIELD_CLIENT_SECRET

    @property
    def mock_mode(self) -> bool:
        return not (self.base_url and self.client_id and self.client_secret)

    def authenticate(self) -> str:
        if self.mock_mode:
            return "MOCK_TOKEN_NO_REAL_PURE_CREDENTIALS"
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
            return data["PolicyList"]
        resp = requests.get(
            f"{self.base_url}/api/policies",
            headers={"Authorization": f"Bearer {token}"},
            params={"clientRef": client_ref},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["PolicyList"]
