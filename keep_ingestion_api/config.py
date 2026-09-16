"""
Keep Carrier Ingestion API — configuration.

Every value here that says "REPLACE" is a placeholder because this project
does not have real Chubb Studio or PURE partner credentials yet — those are
only issued after Keep is an appointed/approved partner with each carrier
(see the main README for what that process actually requires). Nothing in
this codebase fabricates a real Chubb or PURE endpoint URL; the adapters
run in MOCK_MODE against the sample data in sample_data/ until real
credentials are supplied via environment variables.
"""

import os

# ---------------------------------------------------------------------------
# Chubb Studio — partner API. Real base URL, client ID, and client secret
# are issued during Chubb's partner onboarding process; there is no public,
# guessable endpoint to hardcode here.
# ---------------------------------------------------------------------------
CHUBB_STUDIO_BASE_URL = os.getenv("CHUBB_STUDIO_BASE_URL", "")
CHUBB_STUDIO_CLIENT_ID = os.getenv("CHUBB_STUDIO_CLIENT_ID", "")
CHUBB_STUDIO_CLIENT_SECRET = os.getenv("CHUBB_STUDIO_CLIENT_SECRET", "")

# ---------------------------------------------------------------------------
# PURE — agent-portal / OneShield-backed. PURE does not expose an open
# public API; realistic access is via an appointed-producer agent portal or
# a negotiated OneShield data-integration agreement. Same placeholder
# pattern as above.
# ---------------------------------------------------------------------------
PURE_ONESHIELD_BASE_URL = os.getenv("PURE_ONESHIELD_BASE_URL", "")
PURE_ONESHIELD_CLIENT_ID = os.getenv("PURE_ONESHIELD_CLIENT_ID", "")
PURE_ONESHIELD_CLIENT_SECRET = os.getenv("PURE_ONESHIELD_CLIENT_SECRET", "")

# ---------------------------------------------------------------------------
# InsurGrid — aggregator, not a direct carrier relationship. A household
# connects one of THEIR carrier logins once through InsurGrid's embedded
# widget; InsurGrid extracts structured dec-page data back to Keep across
# whatever carrier(s) that household actually holds (per InsurGrid's own
# product copy: Auto/Home/Umbrella/Workers Comp/Cyber/Flood/GL, 450+ carrier
# connections). That's the whole point of this tier — it reaches carriers
# Keep has no direct API or appointment with at all (e.g. Farmers, Travelers
# below), not just Chubb/PURE faster. No InsurGrid partner account exists
# yet, so same placeholder pattern as above; see README "Going live" section.
# ---------------------------------------------------------------------------
INSURGRID_BASE_URL = os.getenv("INSURGRID_BASE_URL", "")
INSURGRID_CLIENT_ID = os.getenv("INSURGRID_CLIENT_ID", "")
INSURGRID_CLIENT_SECRET = os.getenv("INSURGRID_CLIENT_SECRET", "")

# ---------------------------------------------------------------------------
# Query engine — keyword maps used by qa_engine.py to parse plain-language
# questions into (carrier, line of business, field) before looking the
# answer up in normalized policy data. Extend these lists as real usage
# turns up phrasings that don't match yet.
#
# Note on InsurGrid: "insurgrid" is deliberately NOT a key here. InsurGrid is
# a data source, not a carrier — Policy.carrier always holds the actual
# underlying carrier (see Farmers/Travelers below, from the InsurGrid mock
# data), with Policy.aggregator_source noting InsurGrid supplied the record.
# Asking "what's my InsurGrid policy" isn't a real question a client would
# ask; asking "what's my Farmers premium" is, and resolves the same way
# regardless of which tier sourced it.
# ---------------------------------------------------------------------------
CARRIER_SYNONYMS = {
    "chubb": "Chubb",
    "pure": "PURE",
    "farmers": "Farmers",
    "travelers": "Travelers",
}

LOB_SYNONYMS = {
    "auto": ["auto", "car", "vehicle"],
    "homeowners": ["home", "house", "dwelling", "homeowner"],
    "umbrella": ["umbrella", "excess liability"],
    "watercraft": ["boat", "watercraft", "vessel", "yacht"],
}

FIELD_SYNONYMS = {
    "premium": ["price", "premium", "cost", "pay"],
    "deductible": ["deductible"],
    "limit": ["limit", "coverage amount", "how much coverage"],
    "renewal": ["renew", "expire", "expiration", "when does"],
}
