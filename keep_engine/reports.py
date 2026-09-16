"""
Keep Engine — turns household + gap_findings into the three real product
outputs (Gap Alerts / Advisor Action Plan / Household Notification) as one
HTML page. Same dark navy/gold/blue theme as the rest of the app (theme.py,
nav.py) and as Keep_Complete_9.16.26.pptx / Keep_Product_Prototype.html.
"""

from datetime import date

from gap_rules import ACTION_VERBS
from theme import BASE_CSS
from nav import render_nav, NAV_CSS

SEV_CLASS = {"high": "badge-high", "medium": "badge-medium", "low": "badge-low"}
SEV_LABEL = {"high": "High", "medium": "Medium", "low": "Low"}
SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


def _alert_card(f: dict) -> str:
    sev = f["severity"]
    return (
        '<div class="alert-card">'
        '<div class="sev"><span class="badge ' + SEV_CLASS[sev] + '">' + SEV_LABEL[sev] + "</span></div>"
        '<div class="body">'
        "<h3>" + f["title"] + "</h3>"
        "<p>" + f["description"] + "</p>"
        '<p class="exposure">Exposure: ' + f["exposure"] + "</p>"
        "</div></div>"
    )


def _plan_item(i: int, f: dict) -> str:
    action = ACTION_VERBS.get(f["rule_id"], "Review with the client.")
    return (
        '<div class="plan-item">'
        '<span class="n">' + str(i).zfill(2) + "</span><strong>" + action + "</strong>"
        "<p>Source finding: " + f["title"] + "</p>"
        "</div>"
    )


def _notif_item(f: dict) -> str:
    return "<li><strong>" + f["title"] + ".</strong> " + f["description"] + "</li>"


def build_report_html(household: dict, findings: list[dict]) -> str:
    findings_sorted = sorted(findings, key=lambda f: SEV_ORDER[f["severity"]])
    alert_cards = "\n".join(_alert_card(f) for f in findings_sorted) or "<p>No findings yet — ingest policy data first.</p>"
    plan_items = "\n".join(_plan_item(i, f) for i, f in enumerate(findings_sorted, start=1)) or "<p>Nothing to act on yet.</p>"
    notif_candidates = [f for f in findings_sorted if f["severity"] in ("high", "medium")][:4]
    notif_items = "\n".join(_notif_item(f) for f in notif_candidates) or "<li>Nothing flagged yet.</li>"

    report_css = """
      .wrap{max-width:880px;margin:0 auto;padding:0 32px 80px;}
      header.top{background:var(--card);border-bottom:1px solid var(--border);color:var(--text);padding:40px 0 30px;text-align:center;}
      header.top .word{font-size:22px;font-weight:800;letter-spacing:5px;margin:0;}
      header.top .rule{width:56px;height:3px;background:var(--gold);border:none;margin:14px auto;}
      header.top h1{font-size:20px;margin:4px 0 4px;font-weight:700;}
      header.top .sub{color:var(--ice);font-size:13px;margin:0;}
      section{padding:30px 0;border-bottom:1px solid var(--border);}
      section:last-child{border-bottom:none;}
      .label{color:var(--blue);font-weight:700;letter-spacing:1.5px;font-size:11.5px;text-transform:uppercase;}
      section h2{font-size:19px;margin:8px 0 14px;color:var(--text);}
      .alert-card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px 20px;margin-bottom:12px;display:flex;gap:14px;align-items:flex-start;}
      .alert-card .sev{flex:0 0 90px;text-align:center;}
      .alert-card .body h3{font-size:14.5px;margin:0 0 4px;color:var(--text);}
      .alert-card .body p{font-size:12.5px;color:var(--muted);margin:0;}
      .alert-card .exposure{font-size:12px;color:var(--ice);font-weight:700;margin-top:6px;}
      .plan-item{background:var(--card);border:1px solid var(--border);border-left:4px solid var(--blue);border-radius:6px;padding:14px 18px;margin-bottom:10px;}
      .plan-item .n{display:inline-block;background:var(--blue);color:#fff;font-family:Cambria,serif;font-weight:700;font-size:11px;border-radius:20px;padding:2px 9px;margin-right:8px;}
      .plan-item p{margin:6px 0 0;font-size:13px;color:var(--muted);}
      .plan-item strong{color:var(--text);}
      .notif{background:var(--navy2);border:1px solid var(--border);border-radius:10px;padding:26px 28px;color:var(--text);}
      .notif .greet{color:var(--ice);font-size:13px;margin:0 0 14px;}
      .notif ol{margin:0;padding-left:20px;}
      .notif li{margin-bottom:12px;font-size:14px;color:var(--ice);}
      .notif li strong{color:var(--text);}
      footer{text-align:center;padding:32px 0 10px;color:var(--muted);font-size:11px;}
    """

    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        "<title>Keep — Coverage Review: " + household["name"] + "</title>"
        "<style>" + BASE_CSS + NAV_CSS + report_css + "</style></head><body>"
        + render_nav("clients")
        + '<header class="top">'
        '<p class="word">KEEP</p><hr class="rule">'
        "<h1>Coverage Review — " + household["name"] + "</h1>"
        '<p class="sub">Generated from ingested policy data · '
        + (household.get("state") or "state not set") + " · " + date.today().isoformat() + "</p>"
        "</header>"
        '<div class="wrap">'
        "<section>"
        '<p class="label">Output 1 · Gap Alerts</p>'
        "<h2>What the engine found, ranked by exposure.</h2>"
        + alert_cards +
        "</section>"
        "<section>"
        '<p class="label">Output 2 · Advisor Action Plan</p>'
        "<h2>Specific, executable next steps.</h2>"
        + plan_items +
        "</section>"
        "<section>"
        '<p class="label">Output 3 · Household Notification</p>'
        "<h2>What actually gets sent to the client.</h2>"
        '<div class="notif">'
        '<p class="greet">Plain-language, client-facing — no jargon, no alarm.</p>'
        "<ol>" + notif_items + "</ol>"
        "</div>"
        "</section>"
        "</div>"
        "<footer>Keep · Generated by the Keep Engine (v0, local/manual mode) · Not a live product screen</footer>"
        "</body></html>"
    )
