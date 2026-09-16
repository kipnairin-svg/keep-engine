"""
Carrier-specific normalization — the actual "understand any carrier's
format" logic, not just a data-transport layer.

Chubb Studio and PURE/OneShield structure the exact same real-world facts
completely differently:

    Chubb:  policyNumber, productLine, premium.annualAmount,
            coverages: [{coverageCode, limit}], deductibles: [{amount}]

    PURE:   PolicyNum, LOBCode, AnnualPremiumAmt,
            CoverageSchedule: [{CovCode, CovLimit}], Deductible.DeductibleAmt

InsurGrid adds a third, different shape again — and a different kind of
difference. Chubb and PURE are each one carrier's own format; InsurGrid is
an aggregator's format wrapping OTHER carriers' data (Farmers, Travelers,
whichever carrier the household actually holds), extracted from dec pages
rather than pulled from that carrier's own system of record:

    InsurGrid: carrier_name, line_of_business, premium_total,
               coverage_limits: [{label, amount}], deductibles: {type: amount}

This file is where that gets reconciled, once, so everything downstream
(qa_engine.py, main.py, and eventually the gap-detection matrix logic) only
ever deals with the single Policy shape defined in models.py.
"""

from datetime import datetime

from models import Policy

# Chubb's coverageCode -> Keep's normalized coverage_limits key
CHUBB_COVERAGE_MAP = {
    "BI": "bodily_injury",
    "PD": "property_damage",
    "DWELL": "dwelling",
    "PP": "personal_property",
}

# Chubb's productLine -> Keep's normalized line_of_business
CHUBB_LOB_MAP = {
    "PersonalAuto": "auto",
    "Homeowners": "homeowners",
    "PersonalUmbrella": "umbrella",
    "Watercraft": "watercraft",
}

# PURE's CovCode -> Keep's normalized coverage_limits key
PURE_COVERAGE_MAP = {
    "UMB-LIAB": "umbrella_liability",
    "HULL": "hull",
    "MAR-LIAB": "marine_liability",
}

# PURE's LOBCode -> Keep's normalized line_of_business
PURE_LOB_MAP = {
    "PersonalAuto": "auto",
    "Homeowners": "homeowners",
    "PersonalUmbrella": "umbrella",
    "Watercraft": "watercraft",
}

# InsurGrid's coverage `label` -> Keep's normalized coverage_limits key
INSURGRID_COVERAGE_MAP = {
    "Bodily Injury per Person": "bodily_injury_per_person",
    "Bodily Injury per Accident": "bodily_injury_per_accident",
    "Property Damage": "property_damage",
    "Dwelling": "dwelling",
    "Personal Property": "personal_property",
}

# InsurGrid's line_of_business -> Keep's normalized line_of_business
INSURGRID_LOB_MAP = {
    "Auto": "auto",
    "Home": "homeowners",
    "Umbrella": "umbrella",
    "Watercraft": "watercraft",
}


def normalize_chubb(raw: dict) -> Policy:
    coverage_limits = {
        CHUBB_COVERAGE_MAP.get(c["coverageCode"], c["coverageCode"]): c["limit"]
        for c in raw.get("coverages", [])
    }
    deductible = raw["deductibles"][0]["amount"] if raw.get("deductibles") else None
    return Policy(
        policy_id=f"chubb-{raw['policyNumber']}",
        carrier="Chubb",
        source_tier="direct_api",
        line_of_business=CHUBB_LOB_MAP.get(raw["productLine"], raw["productLine"].lower()),
        named_insured=raw["namedInsured"]["name"],
        effective_date=raw["effectiveDate"],
        expiration_date=raw["expirationDate"],
        annual_premium=raw["premium"]["annualAmount"],
        deductible=deductible,
        coverage_limits=coverage_limits,
        vehicles=raw.get("vehicles"),
        raw_source_id=raw["policyNumber"],
        ingested_at=datetime.utcnow(),
    )


def normalize_pure(raw: dict) -> Policy:
    coverage_limits = {
        PURE_COVERAGE_MAP.get(c["CovCode"], c["CovCode"]): c["CovLimit"]
        for c in raw.get("CoverageSchedule", [])
    }
    deductible = raw.get("Deductible", {}).get("DeductibleAmt")
    return Policy(
        policy_id=f"pure-{raw['PolicyNum']}",
        carrier="PURE",
        source_tier="direct_api",
        line_of_business=PURE_LOB_MAP.get(raw["LOBCode"], raw["LOBCode"].lower()),
        named_insured=raw["Insured"]["FullName"],
        effective_date=raw["PolicyEffDate"],
        expiration_date=raw["PolicyExpDate"],
        annual_premium=raw["AnnualPremiumAmt"],
        deductible=deductible,
        coverage_limits=coverage_limits,
        vehicles=None,
        raw_source_id=raw["PolicyNum"],
        ingested_at=datetime.utcnow(),
    )


def normalize_insurgrid(raw: dict) -> Policy:
    """
    Note the key difference from normalize_chubb/normalize_pure: `carrier`
    below is NOT "InsurGrid" — it's whatever carrier InsurGrid actually
    extracted (raw["carrier_name"], e.g. "Farmers"). InsurGrid is recorded
    separately in aggregator_source. This is what makes the aggregator tier
    genuinely different from the direct_api tier, not just a third vendor:
    one adapter can yield policies from carriers Keep has no adapter of its
    own for at all.
    """
    coverage_limits = {
        INSURGRID_COVERAGE_MAP.get(c["label"], c["label"]): c["amount"]
        for c in raw.get("coverage_limits", [])
    }
    # InsurGrid's raw deductibles are a {type: amount} dict (e.g. collision
    # vs. comprehensive, or a single all_peril figure) — Policy.deductible
    # is one number, so this takes the first entry as the primary figure,
    # same simplification normalize_chubb makes off its deductibles list.
    deductibles = raw.get("deductibles", {})
    deductible = next(iter(deductibles.values()), None)
    return Policy(
        policy_id=f"insurgrid-{raw['policy_number']}",
        carrier=raw["carrier_name"],
        source_tier="aggregator",
        aggregator_source="InsurGrid",
        line_of_business=INSURGRID_LOB_MAP.get(raw["line_of_business"], raw["line_of_business"].lower()),
        named_insured=raw["named_insured"],
        effective_date=raw["effective_date"],
        expiration_date=raw["expiration_date"],
        annual_premium=raw["premium_total"],
        deductible=deductible,
        coverage_limits=coverage_limits,
        vehicles=None,
        raw_source_id=raw["policy_number"],
        ingested_at=datetime.utcnow(),
    )
