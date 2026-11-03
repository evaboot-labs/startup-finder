# Run it in n8n

[`n8n/startup-finder.json`](../n8n/startup-finder.json) is the same startup finder for n8n. Every Monday at 8 it exports your account search, scores the new companies as startups, exports the founders of the ones it keeps, and writes both lists into a Google Sheet. No AI model and no extra key: the scoring is a Code node. `n8n/build_workflow.py` regenerates the JSON.

## What runs

1. **Every Monday at 8** (or **Run now**) and **Your settings**: the account search, how many companies and people per run, the two tab URLs, and the points.
2. **Startups already in your sheet** (Google Sheets): the companies of earlier runs, so each run only adds new ones.
3. **Export the companies** and **Check the companies export** (Evaboot MCP): the companies of the account search, waited for every 30 seconds.
4. **Score the startups** (Code): the same points as `finder.py score`. **Add to Startups** writes every company, kept or not, with the reason.
5. **Founders search** (Code): the people search for the founders and C-level of the kept startups, like `finder.py people-url`.
6. **Export the founders** and **Check the founders export** (Evaboot MCP): those people with verified emails.
7. **Founder rows** (Code) and **Add to People**: one row per person, without the people outside the search filters.

## Set it up

1. **Make the sheet:** one Google Sheet with two tabs.
   - `Startups`, header row: `Date, Keep, Score, Company, Founded, Employees, Growth 1y %, Why, Website, LinkedIn id`
   - `People`, header row: `Date, Name, Title, Company, Email, Email status, LinkedIn`
2. **Import** the JSON in n8n: *Workflows > Import from file*.
3. **Add two credentials:**
   - **Bearer Auth** named `Evaboot MCP (Bearer)`: your key from [dash.evaboot.com/dash/api/](https://dash.evaboot.com/dash/api/). Select it on the four Evaboot MCP nodes.
   - **Google Sheets** on the three sheet nodes.
4. **Fill in Your settings:** `account_search_url` (your Sales Navigator account search; the example is US software companies of 11 to 50 people, growing 20% or more, hiring), `accounts_per_run`, `people_per_run`, and `startups_tab_url` and `people_tab_url` (each with its `gid`). `profile` holds the points; keep it in step with `STARTUPS.md`. Its `seniority_ids` are LinkedIn's: 320 Owner / Partner, 310 CXO, 300 Vice President, 220 Director. The n8n version has no `titles`.
5. **Test:** set `accounts_per_run` and `people_per_run` to 5, click **Execute workflow** on **Run now**, and read both tabs.
6. **Publish** the workflow to run it every Monday.

## Good to know

- Each run spends 1 Evaboot credit per exported company and per exported person. LinkedIn serves a search in a changing order, so a weekly run can return companies you already have: they cost a credit but are not added twice.
- A run stops with an error when no new company is found or no startup is kept: widen the account search or raise `accounts_per_run`.

Back to the [README](../README.md).
