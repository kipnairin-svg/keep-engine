"""
Keep Engine — the "Engine" in Keep's own Inputs -> Engine -> Outputs
framing (see the Unicorn deck's Engine slide). Sits on top of the Carrier
Ingestion API (../keep_ingestion_api) rather than duplicating it: imports
its adapters, normalize functions, and Policy model directly, and adds
what that project deliberately left out — persistence (db.py), the actual
gap-detection logic (gap_rules.py), and the three real product outputs
(reports.py).

Run it:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8001

Then:
    curl -X POST http://127.0.0.1:8001/households \\
      -H "Content-Type: application/json" -d '{"name": "Whitfield Household", "state": "UT"}'
    curl -X POST http://127.0.0.1:8001/households/1/ingest/chubb
    curl -X POST http://127.0.0.1:8001/households/1/ingest/pure
    curl -X POST http://127.0.0.1:8001/households/1/ingest/insurgrid
    curl http://127.0.0.1:8001/households/1/gaps
    open http://127.0.0.1:8001/households/1/report   # the full 3-part output
    open http://127.0.0.1:8001/dashboard              # every household at a glance

Runs entirely against MOCK_MODE carrier data — see
../keep_ingestion_api/README.md for what's real vs. not about the
underlying carrier connections themselves. This layer's own honesty note:
the SQLite file here is local, unencrypted, single-user — fine for Kip
running pilots on his own machine, not fine for real household PII at any
real scale. See README.md "Before this holds a real household's data."
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import os
import secrets
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "keep_ingestion_api"))
import normalize  # noqa: E402  (from keep_ingestion_api, added to sys.path above)
from adapters.chubb_studio import ChubbStudioAdapter  # noqa: E402
from adapters.insurgrid import InsurGridAdapter  # noqa: E402
from adapters.pure_oneshield import PureOneShieldAdapter  # noqa: E402
from models import Policy  # noqa: E402

import db  # noqa: E402
import gap_rules  # noqa: E402
import reports  # noqa: E402
from intake import render_intake  # noqa: E402
from theme import BASE_CSS, render_page  # noqa: E402
from nav import render_nav, NAV_CSS  # noqa: E402
from fastapi import UploadFile, File  # noqa: E402
from fastapi.responses import Response  # noqa: E402
import csv_upload  # noqa: E402
import pdf_extract  # noqa: E402
import onepager  # noqa: E402


security = HTTPBasic()


def require_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """
    HTTP Basic Auth -- NOT currently wired up to the app (see `app =
    FastAPI(...)` below, which no longer passes this as a dependency).
    Kept here so it's a one-line change to turn back on: add
    `dependencies=[Depends(require_auth)]` back to the FastAPI(...) call.

    Credentials come from environment variables so the real password never
    lives in this source file:
      KEEP_ENGINE_USER      (defaults to "keep")
      KEEP_ENGINE_PASSWORD  (defaults to "changeme-please" -- override this
                              in Render's dashboard before deploying for
                              real; the default is only meant to make local
                              runs work out of the box, never for anything
                              public)

    Heads up: with this off, this app has NO access control. Every
    household's real policy data (names, addresses, premiums, coverage
    limits) is visible to anyone with the URL, and household pages are
    just /households/1, /households/2, etc. -- trivially guessable. Fine
    for a short-lived demo you control the link to; turn auth back on
    before this sits up for any length of time.
    """
    expected_user = os.getenv("KEEP_ENGINE_USER", "keep")
    expected_pass = os.getenv("KEEP_ENGINE_PASSWORD", "changeme-please")
    user_ok = secrets.compare_digest(credentials.username, expected_user)
    pass_ok = secrets.compare_digest(credentials.password, expected_pass)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


app = FastAPI(
    title="Keep Engine",
    description="Household intake -> policy ingestion -> gap detection -> the three real product outputs.",
    version="0.1.0",
)

db.init_db()


def _policy_from_csv_dict(d: dict, fallback_named_insured: str) -> Policy:
    return Policy(
        policy_id=f"csv-{d['carrier'].lower().replace(' ', '')}-{d['raw_source_id']}",
        carrier=d["carrier"],
        source_tier="document_capture",
        line_of_business=d["line_of_business"],
        named_insured=d["named_insured"] or fallback_named_insured,
        effective_date=d["effective_date"],
        expiration_date=d["expiration_date"],
        annual_premium=d["annual_premium"],
        deductible=d["deductible"],
        coverage_limits=d["coverage_limits"],
        raw_source_id=d["raw_source_id"],
        ingested_at=datetime.utcnow(),
    )


ADAPTERS = {
    "chubb": (ChubbStudioAdapter, normalize.normalize_chubb),
    "pure": (PureOneShieldAdapter, normalize.normalize_pure),
    "insurgrid": (InsurGridAdapter, normalize.normalize_insurgrid),
}


class HouseholdCreate(BaseModel):
    name: str
    state: Optional[str] = None


@app.post("/households")
def create_household(req: HouseholdCreate):
    hid = db.create_household(req.name, req.state)
    return {"id": hid, "name": req.name, "state": req.state}


@app.get("/households")
def list_households():
    return db.list_households()


@app.post("/households/{household_id}/ingest/{source}")
def ingest(household_id: int, source: str, client_ref: str = "demo-household-01"):
    household = db.get_household(household_id)
    if not household:
        raise HTTPException(404, "Household not found")
    if source not in ADAPTERS:
        raise HTTPException(400, f"Unknown source '{source}'. Valid: {list(ADAPTERS)}")
    adapter_cls, normalize_fn = ADAPTERS[source]
    adapter = adapter_cls()
    raw = adapter.fetch_policies(client_ref)
    normalized = [normalize_fn(r) for r in raw]
    db.save_policies(household_id, normalized)
    return {
        "household_id": household_id,
        "source": source,
        "mock_mode": adapter.mock_mode,
        "ingested_count": len(normalized),
        "policy_ids": [p.policy_id for p in normalized],
    }


class ManualPolicyInput(BaseModel):
    """
    The real "how do I get MY data in" answer for anyone who isn't Chubb,
    PURE, or InsurGrid — which today is every real household, since all
    three adapters are still mock-only (see ../keep_ingestion_api/README.md).
    This is the Document Capture tier from the deck, done as direct entry
    instead of OCR: read the numbers off a real dec page (or a photo of
    one) and type them in. Same normalized shape everything else uses, so
    it runs through the exact same gap_rules.py as ingested data — nothing
    downstream treats a manually-entered policy any differently.

    coverage_limits keys the gap rules actually look for: "dwelling",
    "personal_property", "umbrella_liability" (or "excess_liability"),
    and "jewelry"/"jewelry_furs"/"valuables"/"scheduled_personal_property"
    for the jewelry sub-limit if the dec page states one. Use whatever
    other keys make sense for other coverages — they'll just be carried
    along without triggering a specific rule.
    """
    carrier: str
    line_of_business: str
    named_insured: str
    effective_date: str
    expiration_date: str
    annual_premium: float
    deductible: Optional[float] = None
    coverage_limits: dict[str, float] = {}
    raw_source_id: str
    vehicles: Optional[list[dict]] = None


@app.post("/households/{household_id}/policies/manual")
def add_manual_policy(household_id: int, req: ManualPolicyInput):
    household = db.get_household(household_id)
    if not household:
        raise HTTPException(404, "Household not found")
    policy = Policy(
        policy_id=f"manual-{req.carrier.lower().replace(' ', '')}-{req.raw_source_id}",
        carrier=req.carrier,
        source_tier="document_capture",
        line_of_business=req.line_of_business,
        named_insured=req.named_insured,
        effective_date=req.effective_date,
        expiration_date=req.expiration_date,
        annual_premium=req.annual_premium,
        deductible=req.deductible,
        coverage_limits=req.coverage_limits,
        vehicles=req.vehicles,
        raw_source_id=req.raw_source_id,
        ingested_at=datetime.utcnow(),
    )
    db.save_policies(household_id, [policy])
    return {"household_id": household_id, "policy_id": policy.policy_id, "source_tier": "document_capture"}


@app.delete("/households/{household_id}")
def remove_household(household_id: int):
    """
    Permanently deletes a household and all of its policies/findings.
    Backs the Clients page's Remove action -- irreversible, so that UI
    confirms with the user before ever calling this.
    """
    deleted = db.delete_household(household_id)
    if not deleted:
        raise HTTPException(404, "Household not found")
    return {"deleted": True, "household_id": household_id}


@app.get("/households/{household_id}/policies")
def get_policies(household_id: int):
    if not db.get_household(household_id):
        raise HTTPException(404, "Household not found")
    return db.get_policies(household_id)


@app.get("/households/{household_id}/gaps")
def get_gaps(household_id: int):
    household = db.get_household(household_id)
    if not household:
        raise HTTPException(404, "Household not found")
    policies = db.get_policies(household_id)
    findings = gap_rules.evaluate(policies, household.get("state"))
    db.save_findings(household_id, findings)
    return findings


@app.get("/households/{household_id}/report", response_class=HTMLResponse)
def get_report(household_id: int):
    household = db.get_household(household_id)
    if not household:
        raise HTTPException(404, "Household not found")
    policies = db.get_policies(household_id)
    findings = gap_rules.evaluate(policies, household.get("state"))
    db.save_findings(household_id, findings)
    return reports.build_report_html(household, findings)


@app.get("/households/{household_id}/onepager")
def get_onepager(household_id: int):
    """
    Downloadable, print-friendly one-page PDF for the client themselves --
    top-level coverage snapshot + the same plain-language findings as the
    report page's Household Notification section, laid out as an actual
    file rather than only readable inside the app. Built from the same
    real policy/gap data as everything else here.
    """
    household = db.get_household(household_id)
    if not household:
        raise HTTPException(404, "Household not found")
    policies = db.get_policies(household_id)
    findings = gap_rules.evaluate(policies, household.get("state"))
    pdf_bytes = onepager.build_onepager_pdf(household, policies, findings)
    safe_name = "".join(c for c in household["name"] if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Keep_Summary_{safe_name}.pdf"'},
    )


@app.get("/csv-template")
def csv_template():
    """Downloadable starter sheet matching what /policies/csv expects."""
    return Response(
        content=csv_upload.TEMPLATE_CSV,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=keep_policy_template.csv"},
    )


@app.post("/households/{household_id}/policies/csv")
async def upload_policies_csv(household_id: int, file: UploadFile = File(...)):
    household = db.get_household(household_id)
    if not household:
        raise HTTPException(404, "Household not found")

    contents = await file.read()
    parsed, results = csv_upload.parse_csv(contents)

    saved_ids = []
    if parsed:
        policies = [_policy_from_csv_dict(d, household["name"]) for d in parsed]
        db.save_policies(household_id, policies)
        saved_ids = [p.policy_id for p in policies]

    added = sum(1 for r in results if r.status == "added")
    errors = [r.dict() for r in results if r.status == "error"]
    return {
        "household_id": household_id,
        "rows_added": added,
        "policy_ids": saved_ids,
        "errors": errors,
    }


@app.post("/households/{household_id}/policies/pdf-extract")
async def extract_policy_pdf(household_id: int, file: UploadFile = File(...)):
    """
    Extracts best-effort fields from a dec-page PDF and returns them for
    the intake form to pre-fill. Does NOT save anything — the human
    reviews and corrects the draft, then saves through the normal
    /policies/manual endpoint, same as typing it in from scratch.
    """
    household = db.get_household(household_id)
    if not household:
        raise HTTPException(404, "Household not found")
    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Empty file.")
    result = pdf_extract.extract_policy_fields(contents)
    return result


@app.get("/intake", response_class=HTMLResponse)
def intake_form():
    """
    Live-entry form for a design-partner pilot meeting: create a household
    and type in policy numbers straight off a dec page, without curl or
    JSON. Posts to the exact same /households and
    /households/{id}/policies/manual endpoints as everything else here.
    """
    return render_intake()


@app.get("/intake/{household_id}", response_class=HTMLResponse)
def intake_form_for_household(household_id: int):
    """
    Same form, but for a household that already exists — skips step 1.
    Used after a dashboard file upload (?prefill=... carries a PDF's
    best-effort extraction for review) and any time you want to add more
    policies to a household you already started.
    """
    household = db.get_household(household_id)
    if not household:
        raise HTTPException(404, "Household not found")
    return render_intake(preset_household=household)


@app.post("/households/from-csv")
async def create_household_from_csv(file: UploadFile = File(...)):
    """
    Dashboard shortcut: upload a policy spreadsheet and skip straight to
    a fully-populated household, no manual household creation first.
    Named after the first row's named_insured, since CSV data is exact
    (unlike PDF extraction) there's no review step — it saves immediately.
    """
    contents = await file.read()
    parsed, results = csv_upload.parse_csv(contents)
    if not parsed:
        errors = [r.dict() for r in results if r.status == "error"]
        raise HTTPException(400, detail={"message": "No valid policy rows found in that CSV.", "errors": errors})

    name = parsed[0]["named_insured"] or f"New Household ({datetime.utcnow().strftime('%b %d, %Y')})"
    hid = db.create_household(name, None)
    policies = [_policy_from_csv_dict(d, name) for d in parsed]
    db.save_policies(hid, policies)
    return {
        "household_id": hid,
        "name": name,
        "rows_added": len(policies),
        "redirect": f"/households/{hid}/report",
    }


@app.post("/households/from-pdf")
async def create_household_from_pdf(file: UploadFile = File(...)):
    """
    Dashboard shortcut: upload a dec-page PDF and get a new household
    created for you, pre-filled with whatever the extractor found —
    landing on /intake/{id} so you review every field before it saves,
    same discipline as the per-household PDF upload.
    """
    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Empty file.")
    result = pdf_extract.extract_policy_fields(contents)
    if not result.get("ok"):
        raise HTTPException(400, detail=result)

    guess_name = f"{result.get('carrier') or 'New'} Household — {datetime.utcnow().strftime('%b %d, %Y')}"
    hid = db.create_household(guess_name, None)
    return {
        "household_id": hid,
        "name": guess_name,
        "redirect": f"/intake/{hid}",
        "prefill": result,
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """
    The Clients list -- every household, its findings count, a link to its
    report, and now Add/Remove: a "+ New Client" shortcut into the manual
    intake form, and a per-row Remove action wired to
    DELETE /households/{id}. Remove is irreversible (drops the household's
    policies and cached findings too), so it always confirms with the user
    client-side before firing.
    """
    households = db.list_households()
    rows = ""
    for h in households:
        policies = db.get_policies(h["id"])
        findings = gap_rules.evaluate(policies, h.get("state"))
        high = sum(1 for f in findings if f["severity"] == "high")
        med = sum(1 for f in findings if f["severity"] == "medium")
        safe_name = h["name"].replace("\\", "\\\\").replace("'", "\\'")
        rows += (
            "<tr><td>" + str(h["id"]) + "</td>"
            "<td>" + h["name"] + "</td>"
            "<td>" + (h.get("state") or "\u2014") + "</td>"
            "<td><span class=\'badge badge-high\'>" + str(high) + " high</span> "
            "<span class=\'badge badge-medium\'>" + str(med) + " medium</span></td>"
            "<td class=\'actions\'>"
            "<a href=\'/households/" + str(h["id"]) + "/report\'>View report \u2192</a>"
            "<a href=\'#\' class=\'remove-link\' onclick=\"removeClient(" + str(h["id"]) + ", '" + safe_name + "'); return false;\">Remove</a>"
            "</td></tr>"
        )
    empty_row = "<tr><td colspan=\'5\' style=\'color:var(--muted);\'>No clients yet \u2014 use + New Client below, or upload a file from Home.</td></tr>"
    clients_css = """
      .clients-toolbar{display:flex;justify-content:flex-end;margin-bottom:16px;}
      .new-client-btn{display:inline-block;background:var(--gold);color:var(--navy);font-weight:700;
        font-size:12.5px;padding:8px 20px;border-radius:20px;text-decoration:none;letter-spacing:.3px;}
      .new-client-btn:hover{opacity:.9;}
      td.actions{display:flex;gap:14px;align-items:center;}
      .remove-link{color:var(--muted);font-weight:600;font-size:12.5px;}
      .remove-link:hover{color:var(--badtext);}
    """
    body = (
        "<h1>Clients</h1>"
        "<div class=\'clients-toolbar\'><a class=\'new-client-btn\' href=\'/intake\'>+ New Client</a></div>"
        "<table><tr><th>ID</th><th>Client</th><th>State</th><th>Findings</th><th></th></tr>"
        + (rows or empty_row) +
        "</table>"
        "<script>"
        "async function removeClient(id, name){"
        "  if(!confirm('Remove ' + name + '? This permanently deletes their policies and findings \u2014 this cannot be undone.')) return;"
        "  try {"
        "    const res = await fetch('/households/' + id, {method:'DELETE'});"
        "    if(!res.ok){ alert('Could not remove that client.'); return; }"
        "    window.location.reload();"
        "  } catch(e) { alert('Remove failed \u2014 is the server running?'); }"
        "}"
        "</script>"
    )
    return render_page("Clients", "clients", body, extra_css=clients_css)


@app.get("/home", response_class=HTMLResponse)
def home():
    """
    The app's actual homepage: quick stats across the whole book, the
    two file-upload shortcuts to start a new client, and the most
    recently added clients. Findings are recomputed live from
    gap_rules.evaluate() rather than read from the cached gap_findings
    table, so the numbers here are always current even for a client
    whose /report page has never been opened.
    """
    households = db.list_households()
    total_high = total_med = total_low = 0
    for h in households:
        policies = db.get_policies(h["id"])
        findings = gap_rules.evaluate(policies, h.get("state"))
        total_high += sum(1 for f in findings if f["severity"] == "high")
        total_med += sum(1 for f in findings if f["severity"] == "medium")
        total_low += sum(1 for f in findings if f["severity"] == "low")

    recent = sorted(households, key=lambda h: h["id"], reverse=True)[:5]
    recent_rows = ""
    for h in recent:
        recent_rows += (
            "<tr><td>" + h["name"] + "</td>"
            "<td>" + (h.get("state") or "\u2014") + "</td>"
            "<td><a href=\'/households/" + str(h["id"]) + "/report\'>View report \u2192</a></td></tr>"
        )
    if not recent_rows:
        recent_rows = "<tr><td colspan=\'3\' style=\'color:var(--muted);\'>No clients yet.</td></tr>"

    stat_css = """
      .stat-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px;}
      .stat-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px 20px;}
      .stat-card .n{font-family:Cambria,serif;font-size:30px;color:var(--text);}
      .stat-card .l{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.6px;margin-top:4px;}
      .upload-row{display:flex;gap:12px;margin-bottom:32px;flex-wrap:wrap;}
      .upload-pill{background:var(--card);border:1px dashed var(--border);color:var(--ice);font-size:13px;font-weight:600;padding:10px 18px;border-radius:20px;cursor:pointer;}
      .upload-pill:hover{border-color:var(--blue);color:var(--text);}
      #home-upload-status{font-size:12.5px;color:var(--muted);align-self:center;}
      h2.section{font-size:15px;color:var(--ice);text-transform:uppercase;letter-spacing:1px;margin:0 0 12px;}
    """

    body = (
        "<h1>Home</h1>"
        "<div class=\'stat-row\'>"
        "<div class=\'stat-card\'><div class=\'n\'>" + str(len(households)) + "</div><div class=\'l\'>Total Clients</div></div>"
        "<div class=\'stat-card\'><div class=\'n\' style=\'color:var(--badtext);\'>" + str(total_high) + "</div><div class=\'l\'>High-Severity Findings</div></div>"
        "<div class=\'stat-card\'><div class=\'n\' style=\'color:var(--warntext);\'>" + str(total_med) + "</div><div class=\'l\'>Medium-Severity Findings</div></div>"
        "<div class=\'stat-card\'><div class=\'n\' style=\'color:#8FA8FF;\'>" + str(total_low) + "</div><div class=\'l\'>Low / Data-Gap Findings</div></div>"
        "</div>"
        "<h2 class=\'section\'>Start a New Client</h2>"
        "<div class=\'upload-row\'>"
        "<label class=\'upload-pill\'>Upload CSV \u2192 New Client"
        "<input type=\'file\' accept=\'.csv\' style=\'display:none\' onchange=\'homeUploadCsv(this)\'></label>"
        "<label class=\'upload-pill\'>Upload PDF \u2192 New Client"
        "<input type=\'file\' accept=\'.pdf\' style=\'display:none\' onchange=\'homeUploadPdf(this)\'></label>"
        "<label class=\'upload-pill\' style=\'cursor:pointer;\' onclick=\'connectCarriers()\'>Connect via Chubb + PURE \u2192 New Client</label>"
        "<span id=\'home-upload-status\'></span>"
        "</div>"
        "<h2 class=\'section\'>Recent Clients</h2>"
        "<table><tr><th>Client</th><th>State</th><th></th></tr>" + recent_rows + "</table>"
        "<script>"
        "async function homeUploadCsv(input){"
        "  if(!input.files.length) return;"
        "  const statusEl = document.getElementById(\'home-upload-status\');"
        "  const fd = new FormData(); fd.append(\'file\', input.files[0]);"
        "  statusEl.textContent = \'Uploading...\';"
        "  try {"
        "    const res = await fetch(\'/households/from-csv\', {method:\'POST\', body: fd});"
        "    const data = await res.json();"
        "    if(!res.ok){ statusEl.textContent = (data.detail && data.detail.message) || \'Upload failed.\'; return; }"
        "    window.location = data.redirect;"
        "  } catch(e) { statusEl.textContent = \'Upload failed \u2014 is the server running?\'; }"
        "}"
        "async function homeUploadPdf(input){"
        "  if(!input.files.length) return;"
        "  const statusEl = document.getElementById(\'home-upload-status\');"
        "  const fd = new FormData(); fd.append(\'file\', input.files[0]);"
        "  statusEl.textContent = \'Reading PDF...\';"
        "  try {"
        "    const res = await fetch(\'/households/from-pdf\', {method:\'POST\', body: fd});"
        "    const data = await res.json();"
        "    if(!res.ok){ statusEl.textContent = (data.detail && data.detail.message) || \'Could not read that PDF.\'; return; }"
        "    const encoded = encodeURIComponent(btoa(JSON.stringify(data.prefill)));"
        "    window.location = data.redirect + \'?prefill=\' + encoded;"
        "  } catch(e) { statusEl.textContent = \'Upload failed \u2014 is the server running?\'; }"
        "}"
        "async function connectCarriers(){"
        "  const statusEl = document.getElementById(\'home-upload-status\');"
        "  try {"
        "    statusEl.textContent = \'Connecting to Chubb Studio...\';"
        "    const hhRes = await fetch(\'/households\', {method:\'POST\', headers:{\'Content-Type\':\'application/json\'}, body: JSON.stringify({name:\'Whitfield Household\', state:\'UT\'})});"
        "    const hh = await hhRes.json();"
        "    await fetch(`/households/${hh.id}/ingest/chubb`, {method:\'POST\'});"
        "    statusEl.textContent = \'Connecting to PURE (OneShield)...\';"
        "    await fetch(`/households/${hh.id}/ingest/pure`, {method:\'POST\'});"
        "    statusEl.textContent = \'Syncing coverage...\';"
        "    window.location = `/households/${hh.id}/report`;"
        "  } catch(e) { statusEl.textContent = \'Connection failed \u2014 is the server running?\'; }"
        "}"
        "</script>"
    )
    return render_page("Home", "home", body, extra_css=stat_css)


@app.get("/")
def root():
    """Bare-URL visits go straight into the app instead of showing raw JSON."""
    return RedirectResponse(url="/home")


@app.get("/status")
def status():
    return {
        "service": "Keep Engine",
        "status": "mock_mode — local SQLite, no real carrier credentials",
        "endpoints": [
            "POST /households",
            "GET /households",
            "POST /households/{id}/ingest/{chubb|pure|insurgrid}",
            "POST /households/{id}/policies/manual",
            "GET /households/{id}/policies",
            "GET /households/{id}/gaps",
            "GET /households/{id}/report",
            "GET /dashboard",
            "GET /home",
        ],
    }
