# SpecIndex Corpus — Top Data Sources

Analysis of `data/national-commercial-projects.json` (652 projects, captured through 2026-07-24).

## Summary

- **782 total source citations** across 652 projects (avg ~1.2 sources/project)
- **153 unique domains**
- Heavily concentrated: top 3 domains account for **68.8%** of all citations

## By category

| Category | Citations | % of total |
| --- | --- | --- |
| Government / permit portal | 557 | 71.2% |
| Local news | 155 | 19.8% |
| Trade / industry press | 65 | 8.3% |
| Wire / press release | 5 | 0.6% |

## Top 10 domains

| Rank | Domain | Citations | % of total | Category |
| --- | --- | --- | --- | --- |
| 1 | alphagis.alpharetta.ga.us | 298 | 38.1% | Government/permit portal — Alpharetta commercial permits (city open data) |
| 2 | apps.dca.ga.gov | 214 | 27.4% | Government/permit portal — Georgia DCA Developments of Regional Impact (DRI) filings |
| 3 | secure.mariettaga.gov | 26 | 3.3% | Government/permit portal — Marietta GIS developments layer |
| 4 | rebusinessonline.com | 23 | 2.9% | Trade/industry press |
| 5 | datacenterdynamics.com | 19 | 2.4% | Trade/industry press |
| 6 | services1.arcgis.com | 7 | 0.9% | Government/permit portal |
| 7 | enr.com | 6 | 0.8% | Trade/industry press (Engineering News-Record) |
| 8 | courant.com | 5 | 0.6% | Local news |
| 9 | al.com | 5 | 0.6% | Local news |
| 10 | bldup.com | 5 | 0.6% | Trade/industry press |

Full 153-domain breakdown: [SpecIndex Top Data Sources](https://docs.google.com/spreadsheets/d/1JlSpaSK1UGVzuT9eU3Icht4ORHJ0YZiYWX4gCl95sAY/edit) (Google Drive).

## Takeaways

- **Corpus is Georgia-permit-heavy today.** The top 3 sources (Alpharetta GIS, Georgia DCA DRI filings, Marietta GIS) are all Georgia government portals — reflects the Georgia beachhead strategy, not a national pattern yet.
- **National coverage rides on a long tail of local news** (137 of 153 domains cite only 1–2 projects each) plus a handful of national trade press (REBusinessOnline, Data Center Dynamics, ENR) for larger/data-center projects.
- **No dedicated spec-book or CSI-classified sources** — all current sources are permit/press coverage, not construction documents. This is why CSI MasterFormat division codes aren't in the schema yet (see `docs/CONTEXT.md` and `docs/technical-architecture.md` roadmap item #10).
