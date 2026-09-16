"""
Keep Engine — Dec-Page PDF Best-Effort Extraction

Uploads a real insurance declarations-page PDF and tries to pull out
carrier, premium, dates, and coverage limits automatically using text
extraction + keyword-anchored regex. This is deliberately NOT
presented as reliable: real dec pages vary wildly in layout across
carriers, so extraction quality varies. Every field this returns is
either a confident match or None — never a guess dressed up as a
finding. The API layer that calls this (main.py's /pdf-extract route)
does not save anything to the database; it hands the extracted draft
back to the intake form so a human reviews and corrects it before
"Add This Policy" actually saves it, same discipline as gap_rules.py's
R3/R4 "we don't know yet" rules.

If the PDF has no extractable text (a pure scanned image with no OCR
layer), this says so honestly instead of returning empty fields that
look like a failed-but-real attempt.
"""

import re
from typing import Optional

import pdfplumber

CARRIER_HINTS = [
    "Chubb", "PURE", "Privilege Underwriters", "AIG", "AIG Private Client",
    "Cincinnati Insurance", "Nationwide", "Vault", "Chubb Personal Risk",
    "Berkley One", "Pacific Specialty", "Travelers", "Farmers", "State Farm",
    "Cincinnati", "Firemans Fund", "Fireman's Fund", "USAA",
]

MONEY = r"\$?\s?([\d][\d,]*(?:\.\d{2})?)"
DATE = r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})"


def _first_group(pattern: str, text: str, flags=re.IGNORECASE) -> Optional[str]:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def _money_near(label_pattern: str, text: str) -> Optional[float]:
    m = re.search(label_pattern + r"[^\n\$\d]{0,25}" + MONEY, text, re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def extract_text(pdf_bytes: bytes) -> str:
    text_parts = []
    with pdfplumber.open(__import__("io").BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_policy_fields(pdf_bytes: bytes) -> dict:
    text = extract_text(pdf_bytes)

    if not text or len(text.strip()) < 20:
        return {
            "ok": False,
            "reason": "no_extractable_text",
            "message": (
                "Couldn't read any text from this PDF — it's likely a scanned "
                "image with no text layer. Try the CSV upload or type the "
                "numbers in manually instead."
            ),
        }

    carrier = None
    for name in CARRIER_HINTS:
        if re.search(re.escape(name), text, re.IGNORECASE):
            carrier = name
            break

    dates = re.findall(DATE, text)
    effective_date = dates[0] if len(dates) >= 1 else None
    expiration_date = dates[1] if len(dates) >= 2 else None

    annual_premium = (
        _money_near(r"total\s+annual\s+premium", text)
        or _money_near(r"annual\s+premium", text)
        or _money_near(r"total\s+premium", text)
        or _money_near(r"\bpremium\b", text)
    )
    deductible = _money_near(r"deductible", text)
    dwelling = _money_near(r"dwelling", text)
    personal_property = (
        _money_near(r"personal\s+property", text)
        or _money_near(r"contents", text)
    )
    umbrella = (
        _money_near(r"umbrella", text)
        or _money_near(r"excess\s+liability", text)
        or _money_near(r"personal\s+liability", text)
    )
    jewelry = (
        _money_near(r"jewelry", text)
        or _money_near(r"valuables", text)
        or _money_near(r"scheduled\s+personal\s+property", text)
    )

    line_of_business = None
    lob_map = {
        "homeowners": r"homeowners|dwelling\s+fire|HO-?3|HO-?5",
        "umbrella": r"umbrella|excess\s+liability",
        "auto": r"\bauto\b|automobile",
        "watercraft": r"watercraft|boat(?:owners)?",
        "jewelry": r"jewelry|valuables?\s+policy",
    }
    for lob, pattern in lob_map.items():
        if re.search(pattern, text, re.IGNORECASE):
            line_of_business = lob
            break

    found_count = sum(
        1 for v in [carrier, effective_date, annual_premium, dwelling, personal_property, umbrella, jewelry]
        if v is not None
    )

    return {
        "ok": True,
        "confidence_note": (
            f"Found {found_count} field(s) with reasonable confidence. "
            "Review every value below before saving — this is a best-effort "
            "read of the PDF, not a guarantee. Blank fields mean nothing "
            "confident was found, not zero."
        ),
        "carrier": carrier,
        "line_of_business": line_of_business,
        "effective_date": effective_date,
        "expiration_date": expiration_date,
        "annual_premium": annual_premium,
        "deductible": deductible,
        "dwelling": dwelling,
        "personal_property": personal_property,
        "umbrella_liability": umbrella,
        "jewelry": jewelry,
    }
