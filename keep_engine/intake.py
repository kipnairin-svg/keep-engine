"""
Keep Engine — Household Intake Form

A single self-contained HTML page (served at GET /intake) that lets Kip
create a household and type in policy numbers straight off a dec page,
or upload a CSV/PDF instead — live, in front of an advisor. Talks to the
same endpoints as everything else in main.py, so nothing downstream
(gap_rules.py, reports.py) treats data entered here any differently than
data that came from an adapter.

Styled to match Keep_Complete_9.16.26.pptx and Keep_Product_Prototype.html
via theme.py / nav.py, so this looks like the same product as the deck
and the demo dashboard, not a separate light-mode tool.
"""

from theme import BASE_CSS
from nav import render_nav, NAV_CSS

INTAKE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Keep Engine — New Household Intake</title>
<style>
{BASE_CSS}
{NAV_CSS}
  header.top{padding:26px 0 6px;text-align:center;}
  header.top h1{font-size:16px;margin:2px 0 0;font-weight:600;color:var(--ice);}
  .wrap{max-width:640px;margin:0 auto;padding:22px 24px 90px;}
  .card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:22px 24px;margin-bottom:20px;}
  .card h2{font-size:16px;color:var(--text);margin:0 0 14px;}
  label{display:block;font-size:12px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin:12px 0 4px;}
  label:first-child{margin-top:0;}
  input,select{width:100%;padding:9px 10px;border:1px solid var(--border);border-radius:6px;font-size:14px;font-family:inherit;background:var(--bg);color:var(--text);}
  input::placeholder{color:var(--muted);}
  input:focus,select:focus{outline:2px solid var(--blue);outline-offset:-1px;}
  .row2{display:grid;grid-template-columns:1fr 1fr;gap:14px;}
  button{cursor:pointer;border:none;border-radius:7px;padding:11px 18px;font-size:14px;font-weight:700;font-family:inherit;}
  .btn-primary{background:var(--blue);color:#fff;width:100%;margin-top:18px;}
  .btn-primary:hover{background:#2249c4;}
  .btn-primary:disabled{background:#33406b;color:#8B93B8;cursor:not-allowed;}
  .btn-ghost{background:transparent;color:var(--blue);border:1px solid var(--blue);}
  .btn-gold{background:var(--gold);color:var(--navy);}
  .hidden{display:none;}
  .pill{display:inline-block;background:rgba(43,92,230,.16);color:#8FA8FF;font-size:11px;font-weight:700;border-radius:20px;padding:3px 10px;margin-left:8px;text-transform:none;letter-spacing:0;}
  .policy-list{margin-top:14px;}
  .policy-row{display:flex;justify-content:space-between;align-items:center;padding:9px 12px;background:var(--bg);border:1px solid var(--border);border-radius:7px;margin-bottom:8px;font-size:13px;}
  .policy-row b{color:var(--text);}
  .muted{color:var(--muted);font-size:12.5px;}
  .actions{display:flex;gap:10px;margin-top:8px;}
  .actions a{flex:1;text-align:center;text-decoration:none;padding:12px;font-size:14px;border-radius:7px;display:block;line-height:1.2;}
  #status{font-size:12.5px;margin-top:8px;}
  .err{color:var(--badtext);}
  .ok{color:var(--goodtext);}
  .note{background:rgba(201,162,39,.12);border:1px solid rgba(201,162,39,.35);border-radius:8px;padding:10px 14px;font-size:12px;color:var(--warntext);margin-top:16px;}
  .upload-box{border:1px dashed var(--border);border-radius:8px;padding:14px 16px;background:var(--bg);margin-top:14px;}
  .upload-box label{margin-top:0;}
  .upload-box input[type=file]{font-size:12.5px;padding:6px 4px;color:var(--muted);}
  .divider{margin:22px 0 4px;text-align:center;color:var(--muted);font-size:11px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;}
</style>
</head>
<body>
{NAV_HTML}
<header class="top">
  <h1>Household Intake &mdash; live pilot entry</h1>
</header>
<div class="wrap">

  <div class="card" id="household-card">
    <h2>1. Household</h2>
    <div class="row2">
      <div>
        <label>Household / Client Name</label>
        <input id="h-name" placeholder="e.g. Whitfield Household">
      </div>
      <div>
        <label>State</label>
        <input id="h-state" placeholder="e.g. UT" maxlength="2" style="text-transform:uppercase">
      </div>
    </div>
    <button class="btn-primary" id="create-household-btn" onclick="createHousehold()">Create Household</button>
    <div id="household-status"></div>
  </div>

  <div class="card hidden" id="policy-card">
    <h2>2. Add a Policy <span class="pill" id="household-pill"></span></h2>
    <p class="muted">Upload what you have, or type it in manually below.</p>

    <div class="upload-box">
      <label>Upload a Policy Spreadsheet (CSV)</label>
      <input type="file" id="csv-file" accept=".csv">
      <div class="actions" style="margin-top:8px;">
        <button class="btn-ghost" style="flex:1;" onclick="uploadCsv()">Upload CSV</button>
        <a class="btn-ghost" style="flex:1;padding:11px;text-align:center;" href="/csv-template">Download Template</a>
      </div>
      <div id="csv-status" style="margin-top:6px;font-size:12.5px;"></div>
    </div>

    <div class="upload-box">
      <label>Upload a Dec Page (PDF) &mdash; Auto-Fill &amp; Review</label>
      <p class="muted" style="margin:0 0 8px;">Best-effort read of the PDF. It pre-fills the form below so you can check every value before saving &mdash; nothing here saves automatically.</p>
      <input type="file" id="pdf-file" accept=".pdf">
      <button class="btn-ghost" style="width:100%;margin-top:8px;" onclick="extractPdf()">Extract From PDF</button>
      <div id="pdf-status" style="margin-top:6px;font-size:12.5px;"></div>
    </div>

    <div class="divider">&mdash; or enter manually below &mdash;</div>

    <p class="muted">Read these straight off the declarations page. Leave anything blank if it isn't on the page &mdash; the engine flags missing data honestly instead of guessing.</p>

    <label>Carrier</label>
    <input id="p-carrier" placeholder="e.g. Chubb, PURE, State Farm">

    <label>Line of Business</label>
    <select id="p-lob">
      <option value="homeowners">Homeowners</option>
      <option value="umbrella">Umbrella / Excess Liability</option>
      <option value="auto">Auto</option>
      <option value="watercraft">Watercraft</option>
      <option value="jewelry">Jewelry / Valuables (scheduled)</option>
      <option value="other">Other</option>
    </select>

    <div class="row2">
      <div><label>Effective Date</label><input id="p-eff" type="date"></div>
      <div><label>Expiration Date</label><input id="p-exp" type="date"></div>
    </div>

    <div class="row2">
      <div><label>Annual Premium ($)</label><input id="p-premium" type="number" placeholder="e.g. 8400"></div>
      <div><label>Deductible ($, optional)</label><input id="p-deductible" type="number" placeholder="e.g. 5000"></div>
    </div>

    <p class="muted" style="margin-top:16px;font-weight:700;color:var(--text);">Coverage limits on this policy (leave blank if not shown / not applicable)</p>
    <div class="row2">
      <div><label>Dwelling ($)</label><input id="c-dwelling" type="number"></div>
      <div><label>Personal Property ($)</label><input id="c-personal" type="number"></div>
    </div>
    <div class="row2">
      <div><label>Umbrella / Excess Liability ($)</label><input id="c-umbrella" type="number"></div>
      <div><label>Jewelry / Valuables Sub-limit ($)</label><input id="c-jewelry" type="number"></div>
    </div>

    <button class="btn-primary" id="add-policy-btn" onclick="addPolicy()">Add This Policy</button>
    <div id="policy-status"></div>

    <div class="policy-list" id="policy-list"></div>
  </div>

  <div class="card hidden" id="finish-card">
    <h2>3. Review With the Client</h2>
    <div class="actions">
      <a class="btn-gold" id="report-link" href="#" target="_blank">View Coverage Report &rarr;</a>
      <a class="btn-ghost" href="/intake">Start Another Household</a>
    </div>
    <div class="note">Coverage findings are generated live from what you just entered &mdash; nothing here is pre-written. Findings marked "data gap" mean the engine doesn't have enough information to make a claim, not that a gap is confirmed.</div>
  </div>

</div>

<script>

window.__PRESET_HOUSEHOLD__ = __PRESET_HOUSEHOLD_JSON__;
let householdId = null;
let policyCount = 0;

function activateHousehold(id, name, state){
  householdId = id;
  document.getElementById('h-name').value = name;
  if(state) document.getElementById('h-state').value = state;
  document.getElementById('h-name').disabled = true;
  document.getElementById('h-state').disabled = true;
  document.getElementById('create-household-btn').disabled = true;
  document.getElementById('create-household-btn').textContent = "Household Ready";
  document.getElementById('household-pill').textContent = name + (state ? " · " + state : "");
  document.getElementById('policy-card').classList.remove('hidden');
}

async function createHousehold(){
  const name = document.getElementById('h-name').value.trim();
  const state = document.getElementById('h-state').value.trim().toUpperCase();
  const statusEl = document.getElementById('household-status');
  if(!name){ statusEl.textContent = "Enter a household name."; statusEl.className = "err"; return; }
  document.getElementById('create-household-btn').disabled = true;
  try {
    const res = await fetch('/households', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({name: name, state: state || null})
    });
    if(!res.ok) throw new Error('Server error');
    const data = await res.json();
    statusEl.textContent = "Household created.";
    statusEl.className = "ok";
    activateHousehold(data.id, data.name, data.state);
  } catch(e) {
    statusEl.textContent = "Couldn't create household — is the server running?";
    statusEl.className = "err";
    document.getElementById('create-household-btn').disabled = false;
  }
}

async function addPolicy(){
  const statusEl = document.getElementById('policy-status');
  const carrier = document.getElementById('p-carrier').value.trim();
  const lob = document.getElementById('p-lob').value;
  const premium = parseFloat(document.getElementById('p-premium').value) || 0;
  if(!carrier){ statusEl.textContent = "Enter a carrier name."; statusEl.className = "err"; return; }

  const coverage_limits = {};
  const cw = document.getElementById('c-dwelling').value; if(cw) coverage_limits.dwelling = parseFloat(cw);
  const cp = document.getElementById('c-personal').value; if(cp) coverage_limits.personal_property = parseFloat(cp);
  const cu = document.getElementById('c-umbrella').value; if(cu) coverage_limits.umbrella_liability = parseFloat(cu);
  const cj = document.getElementById('c-jewelry').value; if(cj) coverage_limits.jewelry = parseFloat(cj);

  policyCount += 1;
  const body = {
    carrier: carrier,
    line_of_business: lob,
    named_insured: document.getElementById('h-name').value.trim(),
    effective_date: document.getElementById('p-eff').value || "2026-01-01",
    expiration_date: document.getElementById('p-exp').value || "2027-01-01",
    annual_premium: premium,
    deductible: parseFloat(document.getElementById('p-deductible').value) || null,
    coverage_limits: coverage_limits,
    raw_source_id: "intake-" + Date.now() + "-" + policyCount
  };

  try {
    const res = await fetch(`/households/${householdId}/policies/manual`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    if(!res.ok) throw new Error('Server error');
    statusEl.textContent = "Policy added.";
    statusEl.className = "ok";

    const row = document.createElement('div');
    row.className = 'policy-row';
    row.innerHTML = `<span><b>${carrier}</b> — ${lob}</span><span class="muted">$${premium.toLocaleString()}/yr</span>`;
    document.getElementById('policy-list').appendChild(row);

    ['p-carrier','p-eff','p-exp','p-premium','p-deductible','c-dwelling','c-personal','c-umbrella','c-jewelry'].forEach(id => document.getElementById(id).value = '');

    document.getElementById('finish-card').classList.remove('hidden');
    document.getElementById('report-link').href = `/households/${householdId}/report`;
  } catch(e) {
    statusEl.textContent = "Couldn't save that policy — is the server running?";
    statusEl.className = "err";
  }
}

function toDateInput(d){
  const m = (d || '').match(/(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})/);
  if(!m) return '';
  let mm = m[1], dd = m[2], yyyy = m[3];
  if(yyyy.length === 2) yyyy = '20' + yyyy;
  return `${yyyy}-${mm.padStart(2,'0')}-${dd.padStart(2,'0')}`;
}

async function uploadCsv(){
  const statusEl = document.getElementById('csv-status');
  const fileInput = document.getElementById('csv-file');
  if(!fileInput.files.length){ statusEl.textContent = "Choose a CSV file first."; statusEl.className = "err"; return; }
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  statusEl.textContent = "Uploading\u2026";
  statusEl.className = "";
  try {
    const res = await fetch(`/households/${householdId}/policies/csv`, { method: 'POST', body: formData });
    const data = await res.json();
    const label = data.rows_added === 1 ? "policy" : "policies";
    if(data.errors && data.errors.length){
      statusEl.innerHTML = `Added ${data.rows_added} ${label}. ${data.errors.length} row(s) had problems: ` +
        data.errors.map(e => `row ${e.row_number}: ${e.detail}`).join('; ');
      statusEl.className = data.rows_added > 0 ? "ok" : "err";
    } else {
      statusEl.textContent = `Added ${data.rows_added} ${label} from the spreadsheet.`;
      statusEl.className = "ok";
    }
    if(data.rows_added > 0){
      const row = document.createElement('div');
      row.className = 'policy-row';
      row.innerHTML = `<span><b>CSV upload</b> \u2014 ${data.rows_added} ${label} added</span><span class="muted"></span>`;
      document.getElementById('policy-list').appendChild(row);
      document.getElementById('finish-card').classList.remove('hidden');
      document.getElementById('report-link').href = `/households/${householdId}/report`;
    }
  } catch(e) {
    statusEl.textContent = "Upload failed \u2014 is the server running?";
    statusEl.className = "err";
  }
}

function applyExtractedFields(data){
  if(data.carrier) document.getElementById('p-carrier').value = data.carrier;
  if(data.line_of_business) document.getElementById('p-lob').value = data.line_of_business;
  if(data.effective_date) document.getElementById('p-eff').value = toDateInput(data.effective_date);
  if(data.expiration_date) document.getElementById('p-exp').value = toDateInput(data.expiration_date);
  if(data.annual_premium != null) document.getElementById('p-premium').value = data.annual_premium;
  if(data.deductible != null) document.getElementById('p-deductible').value = data.deductible;
  if(data.dwelling != null) document.getElementById('c-dwelling').value = data.dwelling;
  if(data.personal_property != null) document.getElementById('c-personal').value = data.personal_property;
  if(data.umbrella_liability != null) document.getElementById('c-umbrella').value = data.umbrella_liability;
  if(data.jewelry != null) document.getElementById('c-jewelry').value = data.jewelry;
}

async function extractPdf(){
  const statusEl = document.getElementById('pdf-status');
  const fileInput = document.getElementById('pdf-file');
  if(!fileInput.files.length){ statusEl.textContent = "Choose a PDF file first."; statusEl.className = "err"; return; }
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  statusEl.textContent = "Reading PDF\u2026";
  statusEl.className = "";
  try {
    const res = await fetch(`/households/${householdId}/policies/pdf-extract`, { method: 'POST', body: formData });
    const data = await res.json();
    if(!data.ok){
      statusEl.textContent = data.message || "Couldn't read this PDF.";
      statusEl.className = "err";
      return;
    }
    applyExtractedFields(data);
    statusEl.textContent = data.confidence_note + ` Scroll down to review, then click Add This Policy.`;
    statusEl.className = "ok";
    document.getElementById('p-carrier').scrollIntoView({behavior:'smooth', block:'center'});
  } catch(e) {
    statusEl.textContent = "Extraction failed \u2014 is the server running?";
    statusEl.className = "err";
  }
}

(function bootstrap(){
  if(window.__PRESET_HOUSEHOLD__){
    const h = window.__PRESET_HOUSEHOLD__;
    activateHousehold(h.id, h.name, h.state);
    document.getElementById('household-status').textContent = "Continuing this household.";
    document.getElementById('household-status').className = "ok";
  }
  const params = new URLSearchParams(window.location.search);
  const prefillParam = params.get('prefill');
  if(prefillParam){
    try {
      const data = JSON.parse(atob(decodeURIComponent(prefillParam)));
      applyExtractedFields(data);
      const statusEl = document.getElementById('pdf-status');
      statusEl.textContent = (data.confidence_note || `Pre-filled from the uploaded PDF.`) + ` Review every field, then click Add This Policy.`;
      statusEl.className = "ok";
    } catch(e) { /* malformed or missing prefill param \u2014 ignore */ }
  }
})();

</script>
</body>
</html>"""


def render_intake(preset_household: dict = None) -> str:
    """
    Renders the intake page. Pass preset_household (a dict with id/name/state,
    e.g. from db.get_household()) to skip step 1 and jump straight into
    step 2 for an already-existing household -- used by GET /intake/{id},
    including the redirect after a dashboard file upload.
    """
    import json as _json
    preset_json = _json.dumps(preset_household) if preset_household else "null"
    html = INTAKE_HTML.replace("__PRESET_HOUSEHOLD_JSON__", preset_json)
    html = html.replace("{BASE_CSS}", BASE_CSS)
    html = html.replace("{NAV_CSS}", NAV_CSS)
    html = html.replace("{NAV_HTML}", render_nav(""))
    return html
