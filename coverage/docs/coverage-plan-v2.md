**SPECINDEX**

**Coverage Plan v2.0**

**Adapters do the structured work. Agents do the judgment work. Cron keeps it fresh.**

| **Field** | **Value** |
| :-: | :-: |
| Document ID | SPX-COV-001 |
| Version | 2.0 (supersedes 1.1) |
| Date | August 6, 2026 |
| Author | Asif Hussain, drafted with Claude |
| Scope | Data coverage: sources, pipelines, build plan. Not GTM, not pricing. |
| Evidence base | 197 verified sources across 8 workbook tabs; 3 live spec-book pulls; 1 end-to-end skill test (Arkansas, 8 projects, 7 spec docs confirmed) |
| Companion | state_spec_document_portals.xlsx (8 tabs) · spec-pull skill |

|  |
| :-: |
| **WHAT THIS DOCUMENT IS**The build plan for SpecIndex coverage: what to build as code adapters, what to run as Claude agents, what to schedule as background tasks, and in what order, targeted at the top 50 metros and top 500 counties. Everything references a verified source in the companion workbook. It is not a product roadmap. |

# **1. The three build types, and which work goes where**

The rule for splitting work: if the source is structured and stable, write an adapter (code, deterministic, cheap to run daily). If the work needs judgment (classify a PDF, hunt a missing doc, repair a dead link), use an agent. If it must happen without you, schedule it.

| **Type** | **What it is** | **Use for** | **Runs on** |
| :-: | :-: | :-: | :-: |
| Adapter | Deterministic code (Python) per source family | APIs, stable HTML listings, file downloads | Your existing GitHub Actions / Cloud Run weekly pipelines, promoted to daily |
| Agent | Claude with the spec-pull skill | Doc classification, gap-fill search, dead-link repair, new-source discovery | On demand + scheduled Cowork tasks |
| Background task | A schedule that fires an adapter or an agent | Freshness without babysitting | GitHub Actions cron (adapters), Cowork scheduled tasks (agents) |

# **2. Adapters: build these, in this order**

| **#** | **Adapter** | **Covers** | **Effort** | **Why this order** |
| :-: | :-: | :-: | :-: | :-: |
| A1 | Socrata generic (SODA API, one config per dataset) | 8+ metros now: NYC, Chicago, SF, Seattle, Austin, LA, Orlando, San Antonio-adjacent | Days | One adapter, JSON in, config per resource ID. Instant county wins. |
| A2 | ArcGIS FeatureServer generic | 10+ metros: Denver (commercial-only), DC, Columbus, Nashville, Miami-Dade, Raleigh, Fort Worth, Minneapolis, Las Vegas, Fort Worth | Days | Same shape as A1. A1+A2 together cover ~20 of the top 30 metros. |
| A3 | Tier 1 state bid portals (30 sources, per-portal HTML) | Bid-stage projects + spec books in 21 states | 1-2 weeks | Proven live (MO, ME, DE, AR). This is the spec-book supply line. |
| A4 | SAM.gov API client | All federal construction (GSA, VA, USACE) | Days | Free key, documented API, direct spec attachment URLs. |
| A5 | Accela Citizen Access | 900+ agencies incl. Houston area, Dallas, Phoenix, Clark Co, King Co | 2-3 weeks | The no-open-data metros all live here. Browser-grade headers needed. |
| A6 | Bid Express (after one free info account) | ~20 DOT states' letting docs | 1 week | Volume play; lower priority for lighting/HVAC. |
| A7 | Euna family (Bonfire portals) + OpenGov Procurement slugs | Universities, K-12, hospitals, cities | 1-2 weeks | Per-agency public portals; enumerate slugs. |
| A8 | Carto SQL (Philadelphia) + one-offs (Boston CKAN, San Diego CSV) | Remaining verified feeds | Days | Small, config-driven. |

Skip: QuestCDN (pay per doc), Cloudpermit and MyGovernmentOnline (login-walled), Vendor Registry (sunsetting).

# **3. Agents: the judgment layer (spec-pull skill)**

| **Agent job** | **Trigger** | **What it does** |
| :-: | :-: | :-: |
| Spec classifier | New PDFs from A3/A4/A6 | Types each doc; extracts divisions, basis-of-design brands, "or equal" language, with page cites. CSI structure for buildings, state SS/SP numbering for DOT docs. |
| Gap-fill searcher | Bid-stage project with no spec doc | Runs the stage 4 query patterns; verified working in the Arkansas test (found candidates immediately). |
| Dead-link medic | Any 404 in an adapter run | Finds the migrated URL, updates the source table. Portals move (AL, WI did). |
| County platform scout | The 470 TBD counties on the Top 500 Counties tab | Identifies which platform each county's building department runs, attaches it to an adapter. Batch 20-30 counties per run. |
| Source re-verifier | Quarterly | Re-checks all 197 sources, updates the workbook. |

# **4. Background tasks: the schedule**

| **Cadence** | **Task** | **Type** |
| :-: | :-: | :-: |
| Daily | A1/A2/A4 API pulls (cheap JSON); Tier 1 bid-portal delta check | Adapter (GitHub Actions cron) |
| Weekly | Full A3 spec-book crawl; spec classifier over new docs; gap-fill searcher over the week's misses | Adapter + agent |
| Weekly | County platform scout: one batch of 25 TBD counties | Agent (Cowork scheduled task) |
| Monthly | Dead-link sweep across all source tables | Agent |
| Quarterly | Full source re-verification + workbook refresh | Agent |

# **5. Coverage targets (from the new workbook tabs)**

| **Target** | **Today** | **After A1+A2** | **After A5** |
| :-: | :-: | :-: | :-: |
| Top 50 metros with a live permit source | ~24 verified, 4 partial, 2 portal-only | ~30 | ~40+ |
| Top 500 counties with a dedicated feed | 24 verified (470 TBD) | ~35 | 100+ (Accela alone; scout fills the rest) |
| Bid-stage projects with spec docs | 3 states proven | n/a | 21 states weekly via A3 |

|  |
| :-: |
| **HONEST ABOUT THE NUMBERS**County populations are mixed 2020-2025 vintages and the coverage counts reflect this workbook's mapping, not a field audit. "City only" feeds (Chicago, Seattle, Boston, Minneapolis and others) miss suburban county permits; don't count a county as covered until its own volume shows up in the index. |

# **6. 90 days, restated**

| **Window** | **Ship** |
| :-: | :-: |
| Days 1-30 | A1, A2, A4, A8. Spec classifier agent on MO/ME/DE/AR docs. Funnel dashboard: projects → docs → spec docs → recovered. |
| Days 31-60 | A3 all 30 Tier 1 portals. Gap-fill + dead-link agents scheduled. County scout starts (25/week). |
| Days 61-90 | A5 Accela. A6 after Bid Express account. A7 Euna/OpenGov. Openness score v2 from classifier output. |

☐  Every adapter writes to the same project schema with source URL + fetch date
☐  Every brand claim carries a page-level citation
☐  Funnel dashboard live and quoted in design-partner demos
☐  County TBD count dropping every week (470 → under 300 by day 90)

|  |
| :-: |
| **THE RULE**Public data only, every fact cited to its public source. No accounts created by automation, no paid plan rooms, nothing from any prior employer. The one free account (Bid Express) gets made by a human and its terms of use checked before automation touches it. |

|  |
| :-: |
| **IN ONE LINE**Two generic API adapters buy ~20 metros in days, the Tier 1 crawler buys the spec-book moat in weeks, the Accela adapter buys the dark metros, and a weekly agent loop keeps all 197 sources alive without you. |
