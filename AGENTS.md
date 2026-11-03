# Agent instructions

This repo finds startups on LinkedIn and the people to reach in them. It runs a Sales Navigator account search for young, growing companies, exports them with Evaboot, scores each one as a startup with the points in `STARTUPS.md` (founded year, headcount growth, revenue, company type, services firms out), then exports the founders and C-level of the startups it keeps, with verified emails. The user does the outreach. When the user asks to find startups, build a startup prospect list, or reach startup founders:

1. Follow the skill in `skills/startup-finder/SKILL.md` step by step.
2. Read `STARTUPS.md` for the account search, the points and who to reach. If it says `Status: EXAMPLE`, ask the user and update it.
3. Use `finder.py` to score the companies, build the people search and write the lists. The Evaboot MCP server does the Sales Navigator work (`.mcp.json`).
4. If the user is not connected yet, follow `docs/connect-your-agent.md` with them.
5. If the user wants n8n instead, follow `docs/n8n.md` with them one step at a time: you cannot click inside n8n, so say exactly what to do and wait for their confirmation.

Exports cost 1 Evaboot credit per company or lead. Confirm with the user before every export. Never contact anyone yourself. Never ask for or handle an API key: the user writes it into `.env`. Never commit `.env`, `data/` or `lists/`: they hold real people's data.
