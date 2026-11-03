"""Builds n8n/startup-finder.json. Run: python3 n8n/build_workflow.py

Every Monday at 8 (or on Run now), Evaboot exports the companies of your Sales Navigator account search, a Code node
scores each one as a startup like finder.py (founded year, headcount growth, revenue, company type, services words)
and skips the companies already in your sheet, a second Code node builds the people search for the founders and
C-level of the kept startups, Evaboot exports them with verified emails, and both lists land in your Google Sheet.
"""
import json
import uuid
from pathlib import Path

MCP = "https://mcp.evaboot.com/mcp"
EVABOOT_CRED = {"httpBearerAuth": {"id": "", "name": "Evaboot MCP (Bearer)"}}
SHEETS_CRED = {"googleSheetsOAuth2Api": {"id": "", "name": "Google Sheets account"}}
ACCOUNT_SEARCH = ("https://www.linkedin.com/sales/search/company?query=(filters%3AList((type%3ACOMPANY_HEADCOUNT%2Cvalues"
                  "%3AList((id%3AC%2Ctext%3A11-50%2CselectionType%3AINCLUDED)))%2C(type%3AREGION%2Cvalues%3AList((id%3A"
                  "103644278%2Ctext%3AUnited%2520States%2CselectionType%3AINCLUDED)))%2C(type%3AINDUSTRY%2Cvalues%3AList("
                  "(id%3A4%2Ctext%3ASoftware%2520Development%2CselectionType%3AINCLUDED)))%2C(type%3ACOMPANY_HEADCOUNT_GROWTH"
                  "%2CrangeValue%3A(min%3A20))%2C(type%3AJOB_OPPORTUNITIES%2Cvalues%3AList((id%3AJO1%2Ctext%3AHiring%2520on"
                  "%2520Linkedin%2CselectionType%3AINCLUDED)))))")
PROFILE = {"founded_after": 2020, "growth_min": 20, "growth_high": 50, "revenue_max_musd": 10, "keep_score": 5,
           "exclude_types": ["Public Company", "Sole Proprietorship", "Government Agency", "Nonprofit", "Educational"],
           "services_words": ["consulting", "consultancy", "agency", "outsourcing", "staffing", "services partner"],
           "seniority_ids": [320, 310]}

nodes, connections = [], {}


def node(name, type_, version, params, pos, creds=None, **extra):
    n = {"parameters": params, "id": str(uuid.uuid4()), "name": name, "type": type_,
         "typeVersion": version, "position": pos, **extra}
    if creds:
        n["credentials"] = creds
    nodes.append(n)


def link(a, b, out=0):
    connections.setdefault(a, {}).setdefault("main", [])
    while len(connections[a]["main"]) <= out:
        connections[a]["main"].append([])
    connections[a]["main"][out].append({"node": b, "type": "main", "index": 0})


def mcp_call(name, tool, json_expr, pos):
    node(name, "@n8n/n8n-nodes-langchain.mcpClient", 1.1, {
        "endpointUrl": MCP, "authentication": "bearerAuth",
        "tool": {"__rl": True, "mode": "list", "value": tool, "cachedResultName": tool},
        "inputMode": "json", "jsonInput": json_expr, "options": {"timeout": 120000},
    }, pos, EVABOOT_CRED, executeOnce=True)


def code(name, js, pos, **extra):
    node(name, "n8n-nodes-base.code", 2, {"jsCode": js}, pos, **extra)


def is_equal(name, left, right, pos):
    node(name, "n8n-nodes-base.if", 2.2, {"conditions": {
        "options": {"caseSensitive": True, "typeValidation": "loose", "version": 2},
        "conditions": [{"id": str(uuid.uuid4()), "leftValue": left, "rightValue": right,
                        "operator": {"type": "string", "operation": "equals"}}],
        "combinator": "and"}, "options": {}}, pos)


def sheet(name, op, pos, **params):
    p = {"operation": op,
         "documentId": {"__rl": True, "mode": "url", "value": "={{ $('Your settings').first().json.%s }}" % params.pop("tab")},
         "options": {}, **params}
    p["sheetName"] = {"__rl": True, "mode": "url", "value": p["documentId"]["value"]}
    extra = {"alwaysOutputData": True, "executeOnce": True} if op == "read" else {}
    node(name, "n8n-nodes-base.googleSheets", 4.7, p, pos, SHEETS_CRED, **extra)


def poll(prefix, launch, pos):
    """Wait, check the export, loop until it is done; stop on a failed export."""
    x, y = pos
    node(f"Wait 30 s ({prefix})", "n8n-nodes-base.wait", 1.1, {"amount": 30}, [x, y])
    mcp_call(f"Check the {prefix} export", "get_export",
             "={{ JSON.stringify({ extraction_id: $('%s').first().json.structuredContent.result.extraction_id }) }}" % launch,
             [x + 220, y])
    is_equal(f"{prefix.capitalize()} done?", "={{ $json.structuredContent.result.status }}", "EXECUTED", [x + 440, y])
    code(f"Still running? ({prefix})", r"""
// Stop instead of waiting forever when the export failed.
const r = $json.structuredContent.result;
if (r.failure_reason || /FAIL|ERROR|CANCEL/i.test(r.status || '')) throw new Error(`The export stopped: ${r.status} ${r.failure_reason || ''}`);
return [$input.first()];
""", [x + 440, y + 180])
    link(launch, f"Wait 30 s ({prefix})")
    link(f"Wait 30 s ({prefix})", f"Check the {prefix} export")
    link(f"Check the {prefix} export", f"{prefix.capitalize()} done?")
    link(f"{prefix.capitalize()} done?", f"Still running? ({prefix})", out=1)
    link(f"Still running? ({prefix})", f"Wait 30 s ({prefix})")


SCORE_JS = r"""
// Same points as finder.py score: founded year, headcount growth, revenue, company type, services words.
const P = JSON.parse($('Your settings').first().json.profile);
const seen = new Set($('Startups already in your sheet').all().map(i => String(i.json['LinkedIn id'] || '')).filter(Boolean));
const num = v => { const n = parseFloat(String(v ?? '').replace(/[,%]/g, '')); return isNaN(n) ? null : n; };
const today = $now.toFormat('yyyy-MM-dd');
const out = [];
for (const c of $json.structuredContent.result.prospects || []) {
  const id = String(c['Company Linkedin URL Unique ID'] || '').replace(/\/$/, '').split('/').pop();
  if (seen.has(id)) continue;
  let pts = 0, why = [], drop = '';
  if (c['Matches Filters'] === 'no_match') drop = `does not match the search (${c['No Match Reasons']})`;
  else if (P.exclude_types.includes(c['Company Type'])) drop = `${c['Company Type']}, not a venture startup`;
  else {
    const f = num(c['Company Year Founded']);
    if (f && f >= P.founded_after) { pts += 3; why.push(`founded ${f}`); }
    else why.push(f ? `founded ${f}, before ${P.founded_after}` : 'no founding year on LinkedIn');
    const g = num(c['Company Employee Growth 1 Year (%)']);
    if (g !== null && g >= P.growth_high) { pts += 3; why.push(`+${g}% staff in 1 year`); }
    else if (g !== null && g >= P.growth_min) { pts += 2; why.push(`+${g}% staff in 1 year`); }
    const r = num(c['Company Revenue Max (Millions USD)']);
    if (r !== null && r <= P.revenue_max_musd) { pts += 1; why.push(`revenue under $${r}M`); }
    if (c['Company Type'] === 'Privately Held') { pts += 1; why.push('privately held'); }
    const text = `${c['Company Description'] || ''} ${c['Company Specialities'] || ''}`.toLowerCase();
    const hit = P.services_words.filter(w => text.includes(w));
    if (hit.length) { pts -= 3; why.push(`reads like a services firm (${hit.join(', ')})`); }
  }
  out.push({ json: { Date: today, Keep: !drop && pts >= P.keep_score ? 'yes' : 'no', Score: drop ? '' : pts,
    Company: c['Company Name'] || '', Founded: c['Company Year Founded'] || '', Employees: c['Company Employee Range'] || '',
    'Growth 1y %': c['Company Employee Growth 1 Year (%)'] || '', Why: drop || why.join('; '),
    Website: c['Company Website URL'] || '', 'LinkedIn id': id } });
}
if (!out.length) throw new Error('No new company in this run: every company is already in your sheet.');
return out.sort((a, b) => (a.json.Keep !== 'yes') - (b.json.Keep !== 'yes') || (b.json.Score === '' ? -99 : b.json.Score) - (a.json.Score === '' ? -99 : a.json.Score));
"""

PEOPLE_JS = r"""
// Same as finder.py people-url: the founders and C-level of the kept startups.
const P = JSON.parse($('Your settings').first().json.profile);
const ids = $('Score the startups').all().filter(i => i.json.Keep === 'yes').map(i => i.json['LinkedIn id']);
if (!ids.length) throw new Error('No startup kept this week: loosen the profile or raise accounts_per_run.');
const enc = s => encodeURIComponent(encodeURIComponent(s));
const comp = ids.map(i => `(id%3A${enc('urn:li:organization:' + i)}%2CselectionType%3AINCLUDED)`).join('%2C');
const sen = P.seniority_ids.map(s => `(id%3A${s}%2CselectionType%3AINCLUDED)`).join('%2C');
const url = 'https://www.linkedin.com/sales/search/people?query=(filters%3AList('
  + `(type%3ACURRENT_COMPANY%2Cvalues%3AList(${comp}))%2C(type%3ASENIORITY_LEVEL%2Cvalues%3AList(${sen}))))`;
return [{ json: { url, startups: ids.length } }];
"""

ROWS_JS = r"""
// One row per founder or head; people outside the search filters are dropped.
const today = $now.toFormat('yyyy-MM-dd');
const rows = ($json.structuredContent.result.prospects || [])
  .filter(p => !['no', 'no_match'].includes(String(p['Matches Filters'] || '').toLowerCase()))
  .map(p => ({ json: { Date: today, Name: p['Full Name'] || '', Title: String(p['Current Job'] || '').trim(),
    Company: p['Company Name'] || '', Email: p['Email'] || '', 'Email status': p['Email Status'] || 'not found',
    LinkedIn: p['Linkedin URL Public'] || '' } }));
if (!rows.length) throw new Error('No founder or head found inside the filters.');
return rows;
"""

node("Every Monday at 8", "n8n-nodes-base.scheduleTrigger", 1.2, {"rule": {"interval": [
    {"field": "weeks", "triggerAtDay": [1], "triggerAtHour": 8}]}}, [0, 0])
node("Run now", "n8n-nodes-base.manualTrigger", 1, {}, [0, 200])
node("Your settings", "n8n-nodes-base.set", 3.4, {"assignments": {"assignments": [
    {"id": str(uuid.uuid4()), "name": k, "type": t, "value": v} for k, t, v in [
        ("account_search_url", "string", ACCOUNT_SEARCH),
        ("accounts_per_run", "number", 25),
        ("people_per_run", "number", 25),
        ("startups_tab_url", "string", "PASTE_THE_STARTUPS_TAB_URL_WITH_GID"),
        ("people_tab_url", "string", "PASTE_THE_PEOPLE_TAB_URL_WITH_GID"),
        ("profile", "string", json.dumps(PROFILE)),
    ]]}, "options": {}}, [220, 100])
sheet("Startups already in your sheet", "read", [440, 100], tab="startups_tab_url")
mcp_call("Export the companies", "export_sn_search_or_list",
         "={{ JSON.stringify({ search_url: $('Your settings').first().json.account_search_url, "
         "max_results: $('Your settings').first().json.accounts_per_run, "
         "name: 'Startup finder companies ' + $now.toFormat('yyyy-MM-dd') }) }}", [660, 100])
poll("companies", "Export the companies", [880, 100])
code("Score the startups", SCORE_JS, [220, 520])
sheet("Add to Startups", "append", [440, 400], tab="startups_tab_url",
      columns={"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []})
code("Founders search", PEOPLE_JS, [440, 600], executeOnce=True)
mcp_call("Export the founders", "export_sn_search_or_list",
         "={{ JSON.stringify({ search_url: $json.url, max_results: $('Your settings').first().json.people_per_run, "
         "name: 'Startup finder founders ' + $now.toFormat('yyyy-MM-dd') }) }}", [660, 600])
poll("founders", "Export the founders", [880, 600])
code("Founder rows", ROWS_JS, [1540, 600])
sheet("Add to People", "append", [1760, 600], tab="people_tab_url",
      columns={"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []})

for a, b in [("Every Monday at 8", "Your settings"), ("Run now", "Your settings"),
             ("Your settings", "Startups already in your sheet"),
             ("Startups already in your sheet", "Export the companies"),
             ("Score the startups", "Add to Startups"), ("Score the startups", "Founders search"),
             ("Founders search", "Export the founders"), ("Founder rows", "Add to People")]:
    link(a, b)
link("Companies done?", "Score the startups", out=0)
link("Founders done?", "Founder rows", out=0)

workflow = {"name": "Startup finder (Evaboot MCP)", "nodes": nodes, "connections": connections,
            "settings": {"executionOrder": "v1"}, "pinData": {}}
out = Path(__file__).with_name("startup-finder.json")
out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n")
print(out, len(nodes), "nodes")
