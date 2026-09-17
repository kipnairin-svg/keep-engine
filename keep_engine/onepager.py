"""
Keep Engine — downloadable client one-pager.

The "Household Notification" section of reports.py is already the
plain-language, client-facing content — this module takes that same
honesty-first content (real policy data, real findings, no invented
numbers) and lays it out as an actual one-page PDF a client can download,
print, or forward, instead of only being readable inside the app. Light,
print-friendly background (unlike the app's own dark theme) since this is
meant to be printed or read as a standalone document, matching the visual
style of Keep's existing one-sheet exports (Keep_OneSheet_*.pdf).

Deliberately top-level: this is not the advisor's Gap Alerts / Action Plan
view (reports.py's full report) — it is the short, no-jargon summary a
client actually reads. Findings are capped and simplified; anyone who
wants the full technical detail uses the in-app report instead.
"""

from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

NAVY = colors.HexColor("#0F1B3D")
GOLD = colors.HexColor("#C9A227")
BLUE = colors.HexColor("#2B5CE6")
MUTED = colors.HexColor("#5B6178")
TEXT = colors.HexColor("#1B1F2E")
BAD = colors.HexColor("#B23A36")
WARN = colors.HexColor("#8A6D0E")
LOWC = colors.HexColor("#2B5CE6")

SEV_COLOR = {"high": BAD, "medium": WARN, "low": LOWC}
SEV_LABEL = {"high": "Important", "medium": "Worth a look", "low": "For your awareness"}

# Coverage-limit keys worth surfacing on a client-facing one-pager, in the
# order they should appear, with a human label. Anything else in
# coverage_limits is skipped here (still visible in the full report) —
# this page is deliberately not exhaustive.
KEY_LABELS = [
    ("dwelling", "Dwelling"),
    ("personal_property", "Personal Property"),
    ("liability", "Liability"),
    ("umbrella_liability", "Umbrella Liability"),
    ("excess_liability", "Umbrella Liability"),
    ("bodily_injury_per_person", "BI (per person)"),
    ("bodily_injury_per_accident", "BI (per accident)"),
    ("bodily_injury", "Bodily Injury"),
    ("property_damage_per_accident", "PD (per accident)"),
    ("property_damage", "Property Damage"),
    ("jewelry", "Jewelry/Valuables"),
]

LOB_LABEL = {
    "auto": "Auto", "homeowners": "Home", "umbrella": "Umbrella",
    "watercraft": "Watercraft",
}


def _money(v) -> str:
    try:
        return f"${float(v):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _key_limits_str(coverage_limits: dict) -> str:
    if not coverage_limits:
        return "—"
    parts = []
    seen = set()
    for key, label in KEY_LABELS:
        if key in coverage_limits and key not in seen:
            parts.append(f"{label}: {_money(coverage_limits[key])}")
            seen.add(key)
    if not parts:
        # Fall back to whatever is present rather than showing nothing.
        parts = [f"{k.replace('_', ' ').title()}: {_money(v)}" for k, v in list(coverage_limits.items())[:2]]
    return "  ·  ".join(parts[:3])


def _g(p, field):
    return getattr(p, field, None) if hasattr(p, field) else p.get(field)


def build_onepager_pdf(household: dict, policies: list, findings: list[dict]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        topMargin=0.65 * inch, bottomMargin=0.65 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        title=f"Keep — Coverage Summary — {household.get('name', '')}",
    )

    word_style = ParagraphStyle("word", fontName="Helvetica-Bold", fontSize=15, textColor=NAVY, leading=18, letterSpacing=2)
    title_style = ParagraphStyle("title", fontName="Times-Bold", fontSize=19, textColor=NAVY, leading=23, spaceBefore=6)
    sub_style = ParagraphStyle("sub", fontName="Helvetica", fontSize=10, textColor=MUTED, leading=13)
    h2_style = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11.5, textColor=BLUE, leading=14, spaceBefore=16, spaceAfter=8, tracking=0.5)
    body_style = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, textColor=TEXT, leading=13)
    finding_title_style = ParagraphStyle("ftitle", fontName="Helvetica-Bold", fontSize=10, textColor=TEXT, leading=13)
    finding_body_style = ParagraphStyle("fbody", fontName="Helvetica", fontSize=9, textColor=MUTED, leading=12.5, spaceBefore=1)
    tag_style_base = ParagraphStyle("tag", fontName="Helvetica-Bold", fontSize=7.5, leading=9)
    footer_style = ParagraphStyle("footer", fontName="Helvetica", fontSize=8, textColor=MUTED, leading=11)

    elems = []
    elems.append(Paragraph("K E E P", word_style))
    elems.append(HRFlowable(width="100%", thickness=1.4, color=GOLD, spaceBefore=6, spaceAfter=10))
    elems.append(Paragraph(f"Coverage Summary — {household.get('name', 'Household')}", title_style))
    state = household.get("state") or ""
    elems.append(Paragraph(
        f"{state + ' · ' if state else ''}{date.today().strftime('%B %-d, %Y')} · Prepared for your review",
        sub_style,
    ))

    # --- Policies on file -------------------------------------------------
    elems.append(Paragraph("YOUR COVERAGE AT A GLANCE", h2_style))
    rows = [["Line", "Carrier", "Annual Premium", "Key Limits"]]
    for p in policies:
        lob = _g(p, "line_of_business") or ""
        rows.append([
            LOB_LABEL.get(lob, lob.title()),
            _g(p, "carrier") or "—",
            _money(_g(p, "annual_premium")),
            _key_limits_str(_g(p, "coverage_limits") or {}),
        ])
    if len(rows) == 1:
        rows.append(["—", "No policies on file yet", "—", "—"])

    table = Table(rows, colWidths=[0.7 * inch, 1.5 * inch, 1.0 * inch, 3.0 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6FB")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCE1EE")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elems.append(table)

    # --- What we're watching ----------------------------------------------
    elems.append(Paragraph("WHAT WE'RE WATCHING", h2_style))
    sev_order = {"high": 0, "medium": 1, "low": 2}
    ranked = sorted(findings, key=lambda f: sev_order.get(f["severity"], 3))[:4]
    if not ranked:
        elems.append(Paragraph("Nothing flagged yet — add policy data to run a review.", body_style))
    for f in ranked:
        sev = f.get("severity", "low")
        tag_style = ParagraphStyle("tag_" + sev, parent=tag_style_base, textColor=SEV_COLOR.get(sev, LOWC))
        row = Table(
            [[Paragraph(SEV_LABEL.get(sev, "Note").upper(), tag_style),
              Paragraph(f"<b>{f['title']}</b><br/>{f['description']}", finding_body_style)]],
            colWidths=[0.95 * inch, 4.85 * inch],
        )
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#E4E8F2")),
        ]))
        elems.append(row)

    elems.append(Spacer(1, 22))
    elems.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#DCE1EE"), spaceAfter=8))
    elems.append(Paragraph(
        "This summary is a plain-language overview generated from the policy data on file — "
        "it is not your policy contract and doesn't replace it. Questions about any item above? "
        "Talk to your advisor.",
        footer_style,
    ))
    elems.append(Paragraph("Keep · Generated automatically · " + date.today().isoformat(), footer_style))

    doc.build(elems)
    return buf.getvalue()
