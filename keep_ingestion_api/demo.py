"""
No-server demo: ingest both carriers' mock data, then ask it some questions.

    python3 demo.py

This is the fastest way to see the whole thing work end to end without
running uvicorn. It uses the exact same adapters, normalize.py, and
qa_engine.py that main.py's API wraps — nothing here is a separate/simpler
code path.
"""

import normalize
import qa_engine
from adapters.chubb_studio import ChubbStudioAdapter
from adapters.insurgrid import InsurGridAdapter
from adapters.pure_oneshield import PureOneShieldAdapter

DEMO_QUESTIONS = [
    "What is Chubb's auto policy price?",
    "What's the PURE umbrella limit?",
    "When does the Chubb homeowners policy renew?",
    "What's the deductible on the PURE watercraft policy?",
    "What is PURE's auto policy price?",  # PURE isn't ingested for auto in this demo — shows the honest fallback
    "What is Farmers' auto policy price?",  # only reachable via InsurGrid — no direct Farmers adapter exists
    "What's the deductible on the Travelers home policy?",  # same — Travelers has no direct adapter either
]


def main():
    chubb = ChubbStudioAdapter()
    pure = PureOneShieldAdapter()
    insurgrid = InsurGridAdapter()

    print(f"Chubb adapter mock_mode:     {chubb.mock_mode}")
    print(f"PURE adapter mock_mode:      {pure.mock_mode}")
    print(f"InsurGrid adapter mock_mode: {insurgrid.mock_mode}\n")

    store = []
    store += [normalize.normalize_chubb(r) for r in chubb.fetch_policies("demo-household-01")]
    store += [normalize.normalize_pure(r) for r in pure.fetch_policies("demo-household-01")]
    store += [normalize.normalize_insurgrid(r) for r in insurgrid.fetch_policies("demo-household-01")]

    print(f"Ingested {len(store)} policies:")
    for p in store:
        tier_note = f" via {p.aggregator_source}" if p.aggregator_source else ""
        print(f"  - {p.policy_id} | {p.carrier} {p.line_of_business} | ${p.annual_premium:,.0f}/yr | tier: {p.source_tier}{tier_note}")
    print()

    for q in DEMO_QUESTIONS:
        result = qa_engine.answer(q, store)
        print(f"Q: {q}")
        if result["resolved"]:
            print(f"A: {result['answer']}  (source: {result['source_policy_id']}, tier: {result['source_tier']})")
        else:
            print(f"A: [not resolved] {result['message']}")
        print()


if __name__ == "__main__":
    main()
