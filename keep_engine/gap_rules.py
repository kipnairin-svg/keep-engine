"""
Keep Engine — the actual gap-detection logic. This is "the Engine" in
Keep's own Inputs -> Engine -> Outputs framing (see the Unicorn deck's
Engine slide), operating on normalized Policy objects (or the equivalent
dicts loaded back from SQLite) plus basic household metadata (state), and
returning a flat list of findings.

Every rule here traces back to reasoning already done manually, in chat,
against two real households this session (Kip's own policies, and the
Nairin household) — this file turns that same reasoning into re-runnable
code instead of a one-off analysis. Deliberately conservative: several
rules emit a "data gap" finding instead of guessing when the ingested data
doesn't actually contain what's needed to compute a real number — see R3
and R4. That honesty-over-completeness choice matches how every other Keep
document this session has been built.
"""

from typing import Optional

# States with meaningfully elevated earthquake exposure for a residential
# risk conversation — not exhaustive seismic-hazard science, just the
# states worth a prompt. Extend as real usage turns up gaps.
HIGH_SEISMIC_STATES = {"CA", "UT", "WA", "OR", "NV", "AK", "MO", "SC", "TN", "AR"}

JEWELRY_KEYS = {"jewelry", "jewelry_furs", "valuables", "scheduled_personal_property"}
UMBRELLA_KEYS = {"umbrella_liability", "excess_liability"}
DWELLING_KEYS = {"dwelling"}
PERSONAL_PROPERTY_KEYS = {"personal_property"}

ACTION_VERBS = {
    "R1_no_umbrella": "Confirm whether an umbrella policy exists elsewhere; if not, quote one.",
    "R2_umbrella_sizing": "Re-quote the umbrella at a higher limit and present the premium delta — a sizing question, not a compliance one.",
    "R3_jewelry_limit_low": "Identify and appraise items above the blanket limit; move them onto a dedicated schedule.",
    "R3_jewelry_data_gap": "Ask the client directly what they own above typical blanket-limit thresholds — don't assume the dec page covers it.",
    "R4_valuation_staleness_gap": "Ask when insured values were last set; capture a last-valued date so drift can actually be monitored.",
    "R5_earthquake_exclusion": "Quote an earthquake endorsement and present cost vs. exposure directly.",
    "R6_flood_exclusion": "Confirm flood-zone designation for the address; quote NFIP or private flood if in/near a mapped zone.",
}


def _g(p, field):
    """Read a field off either a Policy object or a plain dict (dicts show
    up when policies are loaded back out of SQLite as JSON)."""
    return getattr(p, field, None) if hasattr(p, field) else p.get(field)


def _sum_keys(coverage_limits: dict, keys: set) -> float:
    return sum(v for k, v in (coverage_limits or {}).items() if k in keys)


def evaluate(policies: list, household_state: Optional[str] = None) -> list[dict]:
    findings: list[dict] = []

    homeowners = [p for p in policies if _g(p, "line_of_business") == "homeowners"]
    umbrellas = [p for p in policies if _g(p, "line_of_business") == "umbrella"]

    total_dwelling = sum(_sum_keys(_g(p, "coverage_limits"), DWELLING_KEYS) for p in homeowners)
    total_personal_property = sum(_sum_keys(_g(p, "coverage_limits"), PERSONAL_PROPERTY_KEYS) for p in homeowners)
    total_property_value = total_dwelling + total_personal_property
    total_umbrella_limit = sum(_sum_keys(_g(p, "coverage_limits"), UMBRELLA_KEYS) for p in umbrellas)

    # R1 — no umbrella despite meaningful property value on file
    if total_property_value >= 1_000_000 and not umbrellas:
        findings.append({
            "rule_id": "R1_no_umbrella",
            "severity": "high",
            "title": "No umbrella/excess liability policy on file",
            "description": (
                f"${total_property_value:,.0f} in insured dwelling + personal property, with no umbrella policy "
                "ingested. Could be a real gap, or just not yet connected — worth confirming which."
            ),
            "exposure": "Liability above the homeowners policy's own limits is currently unprotected, as far as ingested data shows.",
        })

    # R2 — umbrella limit small relative to total insured property value
    if umbrellas and total_property_value > 0 and total_umbrella_limit > 0:
        ratio = total_property_value / total_umbrella_limit
        if ratio > 2:
            findings.append({
                "rule_id": "R2_umbrella_sizing",
                "severity": "medium",
                "title": "Umbrella limit may not scale with total insured property value",
                "description": (
                    f"${total_property_value:,.0f} in dwelling + personal property sits under a "
                    f"${total_umbrella_limit:,.0f} umbrella — roughly {ratio:.1f}x. Not automatically wrong, but "
                    "worth sizing against actual net worth rather than leaving it as a legacy figure."
                ),
                "exposure": f"Liability above ${total_umbrella_limit:,.0f} is currently self-retained.",
            })

    # R3 — jewelry/valuables blanket limit: flag a low limit if the data
    # actually has one, otherwise flag the data gap honestly instead of
    # guessing at an exposure number that isn't there.
    for p in homeowners:
        limits = _g(p, "coverage_limits") or {}
        jewelry_val = next((v for k, v in limits.items() if k in JEWELRY_KEYS), None)
        source_id = _g(p, "raw_source_id")
        if jewelry_val is not None and jewelry_val < 5000:
            findings.append({
                "rule_id": "R3_jewelry_limit_low",
                "severity": "medium",
                "title": "Jewelry & valuables blanket limit may be low",
                "description": (
                    f"Homeowners policy ({source_id}) carries a ${jewelry_val:,.0f} jewelry/valuables blanket "
                    "limit — worth confirming against what's actually owned before assuming it's enough."
                ),
                "exposure": f"Uncapped above ${jewelry_val:,.0f} per the standard blanket sub-limit, pending item-level appraisal.",
            })
        elif jewelry_val is None:
            findings.append({
                "rule_id": "R3_jewelry_data_gap",
                "severity": "low",
                "title": "Jewelry & valuables coverage not itemized in ingested data",
                "description": (
                    f"Homeowners policy ({source_id}) doesn't expose a jewelry/valuables sub-limit in the data "
                    "pulled so far — most dec pages don't summarize it. Confirm directly with the client or "
                    "carrier rather than assuming standard-limit exposure."
                ),
                "exposure": "Unknown — this is a data gap, not a confirmed finding.",
            })

    # R4 — valuation staleness (cross-cutting, applies to every insured
    # value, not just jewelry) — Kip's own insight from the pilot runs:
    # the engine can't yet tell if a value was set 6 months or 6 years ago,
    # because no adapter captures a last-valuation date. Emit it as a
    # recommended next data point, not a fabricated drift number.
    if homeowners or umbrellas:
        findings.append({
            "rule_id": "R4_valuation_staleness_gap",
            "severity": "low",
            "title": "Valuation staleness can't be checked yet — no last-valued date ingested",
            "description": (
                "Every insured value here (dwelling, personal property, scheduled items) could be years out of "
                "date, and this engine has no way to tell yet — no adapter currently captures when a value was "
                "last set vs. today. Continuously flagging drift against a market-index assumption is the "
                "intended behavior once that data point exists; until then this is a known limitation, surfaced "
                "on purpose rather than silently assumed away."
            ),
            "exposure": "Unknown — proactive drift monitoring is designed but not yet running.",
        })

    # R5 / R6 — earthquake / flood are standard homeowners exclusions;
    # always worth a prompt, more urgently in higher-seismic states.
    if homeowners:
        seismic = bool(household_state) and household_state.upper() in HIGH_SEISMIC_STATES
        findings.append({
            "rule_id": "R5_earthquake_exclusion",
            "severity": "medium" if seismic else "low",
            "title": "Earthquake coverage not confirmed as purchased",
            "description": (
                "Standard homeowners policies exclude earthquake by default; it has to be added as an "
                "endorsement or separate policy. " + (
                    f"{household_state} carries meaningful seismic risk, which makes this a real, not "
                    "theoretical, conversation." if seismic else "Worth a quick confirmation either way."
                )
            ),
            "exposure": (
                f"Full dwelling/property value (${total_property_value:,.0f}) uncovered for earthquake-caused "
                "loss, if not separately purchased." if total_property_value
                else "Uncovered for earthquake-caused loss, if not separately purchased."
            ),
        })
        findings.append({
            "rule_id": "R6_flood_exclusion",
            "severity": "medium",
            "title": "Flood coverage excluded by default (standard, not policy-specific)",
            "description": (
                "All standard homeowners policies exclude flood. NFIP or private flood eligibility depends on the "
                "property's flood-zone designation, which isn't in the ingested policy data and needs a separate "
                "address-level check."
            ),
            "exposure": "Unknown until flood-zone status is confirmed for this address.",
        })

    return findings
