---
name: startup-finder
description: Find startups on LinkedIn and their founders - run a Sales Navigator account search for young, growing companies through Evaboot (headcount, headcount growth, hiring, optional funding events), score each company as a startup with the points in STARTUPS.md (founded year, growth, revenue, company type, services firms out), then export the founders and C-level of the startups kept, with verified emails. Use when the user asks to find startups, prospect startups, build a startup list, or reach startup founders on LinkedIn.
---

# Startup finder

This skill runs inside a clone of https://github.com/evaboot-labs/startup-finder: it uses the repo's `finder.py`, `STARTUPS.md` and `docs/`. If `finder.py` is not in the working directory, clone the repo and work from there.

You do the Sales Navigator and Evaboot work through the Evaboot MCP server (`https://mcp.evaboot.com/mcp`). Every tool named below is an Evaboot MCP tool. `finder.py` scores the companies, builds the people search and writes the lists, the same way every time.

## Rules

- **You never contact anyone.** The lists tell the user which startups and people to reach; they do it.
- Confirm with the user before each `export_sn_search_or_list`. Show the search and the cost (1 Evaboot credit per exported company or person), then wait for a yes.
- Never invent a fact about a company or a person. The lists show only what the exports hold. Sales Navigator has no "founded year" or "startup" filter: the founded year comes from the export and is checked by `finder.py`.
- Never ask for or paste an API key. The user writes `EVABOOT_API_KEY` into `.env` and exports it before starting the agent (`docs/connect-your-agent.md`).
- Print every Sales Navigator URL as a Markdown link with the URL in angle brackets: `[Open in Sales Navigator](<url>)`.

## Step 0: check the setup

1. If the Evaboot MCP tools are not in this session, walk the user through `docs/connect-your-agent.md`, then ask them to restart the agent from this folder.
2. Otherwise call `get_daily_export_quota`. If `has_valid_salesnav` is false, ask the user to sign in to Evaboot in Chrome, open any Sales Navigator search with the Evaboot extension, and click Export with Evaboot, then call it again.
3. Run `mkdir -p data lists`.
4. Read `STARTUPS.md`. If it says `Status: EXAMPLE`, ask the user which market (country, industry, size) they sell to, which founding year counts as a startup for them, and who they want to reach (founders, or a head of a team). Rewrite the file and set `Status: yours`.

## Step 1: the account search

1. Build the account search with `build_sn_search_from_prompt`: say **account search, companies only**, with the headquarters, industry and headcount from `STARTUPS.md`. Ask the user how many companies they want and pass it as `max_results`. When it answers `building`, poll `get_search_build`. If it starts a company-first job instead, use its `accounts_url`.
2. Add the startup filters the builder leaves out. Insert each one right after `filters:List(` (`filters%3AList(`), followed by a comma (`%2C`), so it lands inside the filter list even when the URL ends with `,keywords:...`:
   - headcount growth, at least 20% in a year: `(type:COMPANY_HEADCOUNT_GROWTH,rangeValue:(min:20))`
   - hiring on LinkedIn: `(type:JOB_OPPORTUNITIES,values:List((id:JO1,selectionType:INCLUDED)))`
   - funding events in the past 12 months, only if the user asks: `(type:ACCOUNT_ACTIVITIES,values:List((id:RFE,selectionType:INCLUDED)))`. Few companies carry it; warn that it can empty the search.

   URL-encode the added text the same way as the rest of the URL (`:` is `%3A`, `,` is `%2C`). Do not add the keyword "startup": few companies describe themselves that way (it cut 475 companies to 1 in our test).
3. Show the URL as a link so the user can open it and see the count.

## Step 2: export and score the companies

1. On a yes, export it with `export_sn_search_or_list` and `max_results` (25 to start), and poll `get_export` with `limit: 0` until it is done.
2. Save it:

```bash
set -a; [ -n "$EVABOOT_API_KEY" ] || . ./.env; set +a
curl -s -H "Authorization: Bearer $EVABOOT_API_KEY" \
  https://api.evaboot.com/v1/extractions/<extraction_id>/ > data/accounts-$(date +%F).json
python3 finder.py score data/accounts-$(date +%F).json --csv lists/accounts-$(date +%F).csv
```

3. Show the table: the kept startups first, then the dropped ones with the reason. Read the description of each kept company: if one is clearly a services firm, an agency or not a startup, say so and remove its id from `data/kept-<date>.txt`.

## Step 3: export the founders

1. `python3 finder.py people-url data/kept-$(date +%F).txt` prints the people search: the kept companies, with the seniority (and titles) from `STARTUPS.md`. Show it as a link.
2. On a yes, export it with `export_sn_search_or_list` and `max_results`, poll `get_export`, and save it to `data/founders-$(date +%F).json` with the same `curl`.
3. `python3 finder.py leads data/founders-$(date +%F).json --csv lists/founders-$(date +%F).csv` writes the list and drops the people outside the filters. Show it, with the email status of each person.

## Every week

Offer the n8n version (`docs/n8n.md`): every Monday it exports the account search, skips the companies already in the user's sheet, scores the new ones and exports their founders into the same sheet.
