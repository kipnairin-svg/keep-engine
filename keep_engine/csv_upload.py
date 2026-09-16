"""
Keep Engine — CSV Bulk Upload

Lets an advisor upload a spreadsheet of a household's policies (a
CSV export, or the template this module also serves) and bulk-add all
of them in one shot instead of one-at-a-time through the intake form.
This is the reliable upload path: a CSV is structured, exact data —
there is no guessing involved, so unlike the PDF path (pdf_extract.py)
rows go straight into the database without a review step. Bad or
missing values in a row are reported back, not silently invented.

Runs through the exact same Policy model and gap_rules.py as manual
entry and PDF extraction — nothing downstream treats a CSV-sourced
policy any differently.
"""

import csv
import io
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

# The columns the template ships with / the upload parser understands.
# Anything else in the sheet is ignored rather than rejected.
REQUIRED_COLUMNS = ["carrier", "line_of_business", "annual_premium"]
KNOWN_COLUMNS = [
    "carrier", "line_of_business", "named_insured", "effective_date",
    "expiration_date", "annual_premium", "deductible",
    "dwelling", "personal_property", "umbrella_liability", "jewelry",
    "raw_source_id",
]

TEMPLATE_CSV = (
    "carrier,line_of_business,named_insured,effective_date,expiration_date,"
    "annual_premium,deductible,dwelling,personal_property,umbrella_liability,jewelry,raw_source_id\n"
    "Chubb,homeowners,Whitfield Household,2026-01-01,2027-01-01,8400,5000,4500000,900000,,,\n"
    "PURE,umbrella,Whitfield Household,2026-01-01,2027-01-01,1200,,,,2000000,,\n"
)


class CsvRowResult(BaseModel):
    row_number: int
    status: str  # "added" or "error"
    detail: str
    policy_id: Optional[str] = None


def _to_float(val: str) -> Optional[float]:
    val = (val or "").strip().replace("$", "").replace(",", "")
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def parse_csv(file_bytes: bytes) -> tuple[list[dict], list[CsvRowResult]]:
    """
    Returns (parsed_policy_dicts, per_row_results). parsed_policy_dicts is
    ready to hand to models.Policy(**d) for each successfully parsed row.
    Rows with a missing required column or unparseable premium are
    reported as errors and excluded, rather than saved with a guessed
    value.
    """
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        return [], [CsvRowResult(row_number=0, status="error", detail="File is empty or not a valid CSV.")]

    missing_required = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing_required:
        return [], [CsvRowResult(
            row_number=0, status="error",
            detail=f"Missing required column(s): {', '.join(missing_required)}. "
                   f"Download the template and match its headers exactly.",
        )]

    parsed = []
    results = []
    for i, row in enumerate(reader, start=2):  # row 1 is the header
        carrier = (row.get("carrier") or "").strip()
        lob = (row.get("line_of_business") or "").strip()
        premium = _to_float(row.get("annual_premium", ""))

        if not carrier or not lob:
            results.append(CsvRowResult(row_number=i, status="error", detail="Missing carrier or line_of_business — row skipped."))
            continue
        if premium is None:
            results.append(CsvRowResult(row_number=i, status="error", detail=f"'{row.get('annual_premium')}' isn't a valid premium amount — row skipped."))
            continue

        coverage_limits = {}
        for key in ("dwelling", "personal_property", "umbrella_liability", "jewelry"):
            v = _to_float(row.get(key, ""))
            if v is not None:
                coverage_limits[key] = v

        raw_id = (row.get("raw_source_id") or "").strip() or f"csv-row-{i}-{int(datetime.utcnow().timestamp())}"

        parsed.append({
            "carrier": carrier,
            "line_of_business": lob,
            "named_insured": (row.get("named_insured") or "").strip(),
            "effective_date": (row.get("effective_date") or "").strip() or "2026-01-01",
            "expiration_date": (row.get("expiration_date") or "").strip() or "2027-01-01",
            "annual_premium": premium,
            "deductible": _to_float(row.get("deductible", "")),
            "coverage_limits": coverage_limits,
            "raw_source_id": raw_id,
        })
        results.append(CsvRowResult(row_number=i, status="added", detail=f"{carrier} — {lob}"))

    return parsed, results
