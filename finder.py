#!/usr/bin/env python3
"""Startup finder: score a Sales Navigator account export as startups, then find their founders.

Usage:
  python3 finder.py score <accounts.json> [--profile STARTUPS.md] [--csv out.csv]
      Scores every company with the points in STARTUPS.md and prints the ranked list (Markdown).
      Writes the kept company ids to data/kept-<date>.txt.
  python3 finder.py people-url <kept.txt> [--profile STARTUPS.md]
      Prints the Sales Navigator people search for the decision makers of the kept companies.
  python3 finder.py leads <leads.json> [--csv out.csv]
      Prints the founders and heads found, with their verified email (Markdown).

<accounts.json> and <leads.json> are Evaboot exports: GET https://api.evaboot.com/v1/extractions/<id>/
"""
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

DEFAULTS = {
    "founded_after": 2020,
    "growth_min": 20,
    "growth_high": 50,
    "revenue_max_musd": 10,
    "keep_score": 5,
    "exclude_types": ["Public Company", "Sole Proprietorship", "Government Agency", "Nonprofit", "Educational"],
    "services_words": ["consulting", "consultancy", "agency", "outsourcing", "staffing", "services partner"],
    "seniority": ["Owner / Partner", "CXO"],
    "titles": [],
}
SENIORITY_IDS = {"Owner / Partner": 320, "CXO": 310, "Vice President": 300, "Director": 220, "Strategic": 130}


def profile(path):
    """Reads the `- key: value` lines of STARTUPS.md over the defaults."""
    p = dict(DEFAULTS)
    if path and Path(path).exists():
        for line in open(path, encoding="utf-8"):
            m = re.match(r"-\s+`?(\w+)`?:\s*(.+)", line.strip())
            if m and m.group(1) in DEFAULTS:
                k, v = m.group(1), m.group(2).strip()
                p[k] = [x.strip() for x in v.split(";") if x.strip()] if isinstance(DEFAULTS[k], list) else float(v)
    return p


def num(v):
    try:
        return float(str(v).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None


def rows(path):
    d = json.load(open(path, encoding="utf-8"))
    return d.get("prospects", d) if isinstance(d, dict) else d


def score_company(c, p):
    """Returns (score, reasons, excluded reason or '')."""
    pts, why = 0, []
    if c.get("Matches Filters") == "no_match":
        return 0, [], f"does not match the search ({c.get('No Match Reasons')})"
    if c.get("Company Type") in p["exclude_types"]:
        return 0, [], f"{c.get('Company Type')}, not a venture startup"
    founded = num(c.get("Company Year Founded"))
    if founded and founded >= p["founded_after"]:
        pts += 3
        why.append(f"founded {int(founded)}")
    elif founded:
        why.append(f"founded {int(founded)}, before {int(p['founded_after'])}")
    else:
        why.append("no founding year on LinkedIn")
    growth = num(c.get("Company Employee Growth 1 Year (%)"))
    if growth is not None and growth >= p["growth_high"]:
        pts += 3
        why.append(f"+{growth:g}% staff in 1 year")
    elif growth is not None and growth >= p["growth_min"]:
        pts += 2
        why.append(f"+{growth:g}% staff in 1 year")
    rev = num(c.get("Company Revenue Max (Millions USD)"))
    if rev is not None and rev <= p["revenue_max_musd"]:
        pts += 1
        why.append(f"revenue under ${rev:g}M")
    if c.get("Company Type") == "Privately Held":
        pts += 1
        why.append("privately held")
    text = f"{c.get('Company Description', '')} {c.get('Company Specialities', '')}".lower()
    hit = [w for w in p["services_words"] if w in text]
    if hit:
        pts -= 3
        why.append(f"reads like a services firm ({', '.join(hit)})")
    return pts, why, ""


def company_id(c):
    return str(c.get("Company Linkedin URL Unique ID", "")).rstrip("/").rsplit("/", 1)[-1]


def cmd_score(path, prof, csv_path):
    p = profile(prof)
    scored = []
    for c in rows(path):
        s, why, out = score_company(c, p)
        keep = not out and s >= p["keep_score"]
        scored.append({"Keep": "yes" if keep else "no", "Score": s if not out else "", "Company": c.get("Company Name", ""),
                       "Founded": c.get("Company Year Founded", ""), "Employees": c.get("Company Employee Range", ""),
                       "Growth 1y %": c.get("Company Employee Growth 1 Year (%)", ""), "Why": out or "; ".join(why),
                       "Website": c.get("Company Website URL", ""), "LinkedIn id": company_id(c)})
    scored.sort(key=lambda r: (r["Keep"] != "yes", -(r["Score"] if r["Score"] != "" else -99)))
    print(f"| Keep | Score | Company | Founded | Employees | Growth 1y | Why |\n|---|---|---|---|---|---|---|")
    for r in scored:
        print(f"| {r['Keep']} | {r['Score']} | {r['Company']} | {r['Founded']} | {r['Employees']} | {r['Growth 1y %']}% | {r['Why']} |")
    kept = [r["LinkedIn id"] for r in scored if r["Keep"] == "yes"]
    out = Path("data") / f"kept-{dt.date.today()}.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(kept) + "\n")
    print(f"\n{len(kept)} of {len(scored)} companies kept. Ids in {out}.")
    if csv_path and scored:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(scored[0].keys()))
            w.writeheader()
            w.writerows(scored)


def cmd_people_url(kept_path, prof):
    p = profile(prof)
    ids = [l.strip() for l in open(kept_path) if l.strip()]
    if not ids:
        sys.exit("No company kept: loosen STARTUPS.md or export more accounts.")
    enc = lambda s: quote(s, safe="")
    comp = "%2C".join(f"(id%3A{enc(enc('urn:li:organization:' + i))}%2CselectionType%3AINCLUDED)" for i in ids)
    parts = [f"(type%3ACURRENT_COMPANY%2Cvalues%3AList({comp}))"]
    unknown = [s for s in p["seniority"] if s not in SENIORITY_IDS]
    if unknown:
        sys.exit(f"Unknown seniority in STARTUPS.md: {', '.join(unknown)}. Use: {'; '.join(SENIORITY_IDS)}")
    sen = [SENIORITY_IDS[s] for s in p["seniority"]]
    if sen and not p["titles"]:  # titles replace the seniority filter
        parts.append("(type%3ASENIORITY_LEVEL%2Cvalues%3AList("
                     + "%2C".join(f"(id%3A{s}%2CselectionType%3AINCLUDED)" for s in sen) + "))")
    if p["titles"]:
        parts.append("(type%3ACURRENT_TITLE%2Cvalues%3AList("
                     + "%2C".join(f"(text%3A{enc(enc(t))}%2CselectionType%3AINCLUDED)" for t in p["titles"]) + "))")
    print("https://www.linkedin.com/sales/search/people?query=(filters%3AList(" + "%2C".join(parts) + "))")


def cmd_leads(path, csv_path):
    out, dropped = [], 0
    for r in rows(path):
        if str(r.get("Matches Filters", "")).lower() in ("no", "no_match"):
            dropped += 1  # LinkedIn served someone outside the search (another company or role)
            continue
        out.append({"Name": r.get("Full Name", ""), "Title": str(r.get("Current Job", "")).strip(),
                    "Company": r.get("Company Name", ""), "Email": r.get("Email", ""),
                    "Email status": r.get("Email Status", "") or "not found", "LinkedIn": r.get("Linkedin URL Public", "")})
    print("| Name | Title | Company | Email status |\n|---|---|---|---|")
    for r in out:
        print(f"| {r['Name']} | {r['Title']} | {r['Company']} | {r['Email status']} |")
    safe = sum(r["Email status"] == "safe" for r in out)
    print(f"\n{len(out)} people kept, {safe} with a safe email. {dropped} dropped: outside the search filters.")
    if csv_path and out:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)


def opt(args, name):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "score":
        cmd_score(a[1], opt(a, "--profile") or "STARTUPS.md", opt(a, "--csv"))
    elif len(a) >= 2 and a[0] == "people-url":
        cmd_people_url(a[1], opt(a, "--profile") or "STARTUPS.md")
    elif len(a) >= 2 and a[0] == "leads":
        cmd_leads(a[1], opt(a, "--csv"))
    else:
        sys.exit(__doc__)
