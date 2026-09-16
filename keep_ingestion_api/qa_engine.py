"""
Ask The Engine — plain-language query resolution over normalized policy
data.

This is real keyword-based parsing, not a lookup table of canned questions.
It pulls (carrier, line of business, field) out of the question text using
the synonym maps in config.py, filters the ingested Policy list down to
whatever matches, and reads the actual value off the matching Policy
object. Ask it something with different wording than the demo questions
below and it will still work, as long as the carrier/LOB/field words are in
config.py's synonym lists — that's the real dividing line for what will and
won't resolve, and it's meant to be obvious rather than magic.
"""

from typing import Optional

from config import CARRIER_SYNONYMS, LOB_SYNONYMS, FIELD_SYNONYMS
from models import Policy


def _match_carrier(q: str) -> Optional[str]:
    for keyword, carrier in CARRIER_SYNONYMS.items():
        if keyword in q:
            return carrier
    return None


def _match_lob(q: str) -> Optional[str]:
    for lob, synonyms in LOB_SYNONYMS.items():
        if any(word in q for word in synonyms):
            return lob
    return None


def _match_field(q: str) -> str:
    for field, synonyms in FIELD_SYNONYMS.items():
        if any(word in q for word in synonyms):
            return field
    return "premium"  # default: most questions about a policy are really about cost


def answer(question: str, policies: list[Policy]) -> dict:
    q = question.lower()
    carrier = _match_carrier(q)
    lob = _match_lob(q)
    field = _match_field(q)

    candidates = [
        p for p in policies
        if (carrier is None or p.carrier == carrier)
        and (lob is None or p.line_of_business == lob)
    ]

    if not candidates:
        return {
            "question": question,
            "resolved": False,
            "message": (
                "No ingested policy matches that yet. Either it hasn't been ingested, "
                "the carrier isn't connected, or the question doesn't include a "
                "recognizable carrier/line-of-business word (see config.py's synonym lists)."
            ),
            "parsed": {"carrier": carrier, "line_of_business": lob, "field": field},
        }

    policy = candidates[0]

    if field == "premium":
        value = f"${policy.annual_premium:,.0f}/yr"
    elif field == "deductible":
        value = f"${policy.deductible:,.0f}" if policy.deductible is not None else "No deductible on file"
    elif field == "limit":
        value = ", ".join(f"{k.replace('_', ' ')}: ${v:,.0f}" for k, v in policy.coverage_limits.items()) or "No coverage limits on file"
    elif field == "renewal":
        value = f"Renews {policy.expiration_date}"
    else:
        value = "Field not recognized"

    return {
        "question": question,
        "resolved": True,
        "answer": value,
        "carrier": policy.carrier,
        "line_of_business": policy.line_of_business,
        "source_policy_id": policy.policy_id,
        "source_tier": policy.source_tier,
        "parsed": {"carrier": carrier, "line_of_business": lob, "field": field},
    }
