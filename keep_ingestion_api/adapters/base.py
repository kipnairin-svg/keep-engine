"""
Shared interface every carrier adapter implements.

Adding a new carrier (a third direct relationship, or a specific aggregator
like Canopy Connect) means writing one new class here that implements
`authenticate()` and `fetch_policies()` — nothing else in the codebase
needs to change, since main.py and qa_engine.py only ever see normalized
Policy objects, not carrier-specific shapes.
"""

from abc import ABC, abstractmethod


class CarrierAdapter(ABC):
    carrier_name: str
    source_tier: str = "direct_api"

    @property
    def mock_mode(self) -> bool:
        """True until real partner credentials are supplied via config.py / env vars."""
        raise NotImplementedError

    @abstractmethod
    def authenticate(self) -> str:
        """Return a bearer token. In mock mode, returns a clearly-labeled fake token."""
        raise NotImplementedError

    @abstractmethod
    def fetch_policies(self, client_ref: str) -> list[dict]:
        """Return this carrier's raw (un-normalized) policy records for a client."""
        raise NotImplementedError
