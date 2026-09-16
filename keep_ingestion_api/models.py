"""
Keep Carrier Ingestion API — normalized policy schema.

This is the shape every carrier's data gets mapped INTO, regardless of how
that carrier structures its own response. Chubb Studio and PURE/OneShield
each use different field names, casing, and nesting for the same real-world
facts (a premium is a premium) — normalize.py's job is to close that gap
once, here, so nothing downstream (the gap-detection matrix logic, the
Ask-The-Engine query layer) ever has to know which carrier a policy came
from.
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class Policy(BaseModel):
    policy_id: str = Field(..., description="Keep's internal ID for this policy (carrier prefix + raw source ID)")
    carrier: str = Field(..., description="'Chubb' or 'PURE' — extend as more carriers/tiers are added")
    source_tier: str = Field(..., description="'direct_api' | 'aggregator' | 'document_capture'")
    line_of_business: str = Field(..., description="'auto' | 'homeowners' | 'umbrella' | 'watercraft' | ...")
    named_insured: str
    effective_date: date
    expiration_date: date
    annual_premium: float
    deductible: Optional[float] = None
    coverage_limits: dict[str, float] = Field(default_factory=dict, description="e.g. {'dwelling': 6200000, 'bodily_injury': 500000}")
    vehicles: Optional[list[dict]] = None
    raw_source_id: str = Field(..., description="The carrier's own policy number, kept for traceability/audit")
    aggregator_source: Optional[str] = Field(
        None,
        description=(
            "Set when source_tier='aggregator' — the aggregator that supplied this record "
            "(e.g. 'InsurGrid'), distinct from `carrier`, which stays the actual underlying "
            "carrier (e.g. 'Farmers') the household's policy is written with."
        ),
    )
    ingested_at: datetime
