# The startups you look for

Status: EXAMPLE

The agent reads this file before every search. Replace the example with your own market, then set `Status: yours`.

## Account search (Sales Navigator filters)

- Headquarters: United States
- Industry: Software Development
- Company headcount: 11-50
- Company headcount growth: at least 20% in one year
- Spotlight: Hiring on LinkedIn
- Optional: Recent activities, Funding events in past 12 months. Few companies carry it (12 software companies of 11-50 people worldwide on 2026-11-03), so add it last, never first.

## Scoring (read by finder.py)

- founded_after: 2020
- growth_min: 20
- growth_high: 50
- revenue_max_musd: 10
- keep_score: 5
- exclude_types: Public Company; Sole Proprietorship; Government Agency; Nonprofit; Educational
- services_words: consulting; consultancy; agency; outsourcing; staffing; services partner

Points: founded in or after `founded_after` +3, one-year headcount growth at or above `growth_min` +2 (at or above `growth_high` +3), revenue at most `revenue_max_musd` million USD +1, privately held +1, description or specialities with a `services_words` word -3. A company is kept at `keep_score` or more. A company that does not match the search, or whose type is in `exclude_types`, is dropped.

## Who to reach at each startup

- seniority: Owner / Partner; CXO
- titles:

Leave `titles` empty to keep founders and C-level. Add titles (separated by `;`) to reach a head of a team instead, for example `Head of Sales; VP Sales`: the titles then replace the seniority filter. Seniority values: Owner / Partner; CXO; Vice President; Director; Strategic.
