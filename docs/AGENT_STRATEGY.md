# SpecIndex Agent Strategy

**The live process is the 11-step loop in Part 1.** Read that first; everything
after it is reference.

> ## DO NOT APPEND CORRECTIONS TO THIS FILE
>
> When the process changes, **edit the step it changes** and add a one-line
> `> **Changed <date>:**` note beside it. Do not add a new section at the end.
>
> This file previously grew by appending four AMENDMENT blocks that corrected
> the body from 300 lines away, so the current truth had to be assembled by
> reading the original plus four overrides in order. Appending is always the
> easier edit and always the wrong one — it moves the cost from the writer to
> every future reader.

Restructured 2026-08-05. The file had grown by appending four AMENDMENT
sections that CORRECTED the body from 300 lines away, and it opened with ~200
lines of pre-build plan that its own line 70 described as "historical record".
A reader had to absorb the original, then four corrections, and apply them
mentally in the right order. Amendments that have been applied are not
amendments — they are the current state, so they now sit with what they amend.
Nothing was deleted; the superseded plan moved to Part 5.

| Part | Contents |
| :- | :- |
| 1 | The 11-step loop — the live process |
| 2 | Corrections in force — what changed, and why |
| 3 | Reference — goals, source behaviour, routine checks |
| 4 | Measured facts with a shelf life (dated; re-measure before relying) |
| 5 | Superseded: the original three-agent plan |

## Companion document

**[`SPECINDEX_STRATEGY.md`](./SPECINDEX_STRATEGY.md)** — the business strategy,
mirrored from Google Docs and versioned here alongside the code.

The division of labour: **the strategy doc decides WHETHER a thing is worth
doing; this file decides HOW.** When they conflict, strategy wins on scope and
this file wins on method.

That distinction has already changed work more than once. This file's Phase I
says "capture documents from jurisdictions"; the strategy doc says a county with
metadata and no document path is not a win — which is why top-10 county chasing
stopped. It cut the other way too: Phase I assumes a JURISDICTION and could not
express "harvest UFGS" or "crawl SAM.gov", so Part 2 exists because the strategy
doc named sources this file had no slot for.

**Re-mirror the doc after any edit.** The two had already drifted once: the
strategy doc still lists the VA PG-18-1 masters as "free .docx, predictable
URLs" when the TIL moved behind Okta (Part 3 has the working path).

---

# Part 1 — The 11-step loop (live process)

## The loop: 4 phases, 11 steps

*Originally "Gemini-Assisted County/State Source Discovery", implemented 2026-07-28.
Renamed because Gemini is one input to step 1, not the process itself.*

Unlike the rest of this doc, this section describes a real, running process —
not a draft plan. This is the actual workflow used to find and wire every new
county/state source added on 2026-07-28 (Wayne MI, Cook IL, Miami-Dade FL,
King WA, Tarrant TX, Franklin/Cuyahoga OH, Mecklenburg/Wake NC, Fairfax VA,
Philadelphia PA, San Diego CA, Dallas/Bexar TX, TDLR TABS statewide TX,
Colorado Springs CO, Cleveland OH). It's now an 11-step loop, **reordered
2026-07-31 into 3 phases per an external review** (recorded in full at
`docs/PIPELINE_REVIEW_2026-07-31.md`) — the step numbers below are not the
order these steps were originally added in; see that doc for the history
and reasoning behind each move. **Steps 8 (document pull), 9 (text
extraction), and 10 (enrichment) are all required for every project pulled
via a structured source, not optional follow-ups** — do not consider a
jurisdiction "done" after step 7 alone, and do not consider an individual
project "done" without steps 8-10. **Step 6 (research fallback) is
conditional, not required for every project** — it only applies when
steps 1-4 find no structured source at all for a jurisdiction.

At a glance, the three phases answer three different questions:

- **Phase I — Source Discovery** (steps 1-4): *Does a live, pullable data
  source exist for this jurisdiction?* Ends with either a confirmed
  source or a logged dead end — never both left open.
- **Phase II — Project Acquisition** (steps 5-7): *Given Phase I's
  answer, how do we turn that into a deduplicated list of real
  candidate projects?* Forks into provider wiring (a source exists) or
  research fallback (it doesn't) — both paths converge on the same
  deduped output before Phase III starts.
- **Phase IV — The Moat** (step 11): *What was CONTESTED?* Runs on
  addenda/amendments and records approved and rejected substitutions with
  dates and citations. Steps 1-10 capture what was specified; only this
  captures who was displaced.
- **Phase III — Project Processing & Enrichment** (steps 8-10): *For
  each new project, what do we now go pull, extract, and enrich to make
  its page useful?* Runs only on what Phase II already deduplicated, so
  nothing here is spent twice on the same project.

### Phase I — Source Discovery

> **Changed 2026-08-04:** Phase I assumes a JURISDICTION, which cannot express
> the highest-yield moat sources — SAM.gov, UFGS, VA masters, owner design
> standards — which are national and document-class-keyed. A **non-jurisdictional
> track** skips county discovery and enters at Phase III.
>
> **Changed 2026-08-05:** step 2 must also assess DOCUMENT FEASIBILITY (is there
> a reachable document path, and if gated, what exactly is the gate) and record
> the endpoint patterns either way. A gated-but-mapped path is valuable intel.


1. **Discovery — Gemini, with context.** Send a query through
   `scripts/gemini_discovery_chat.py --session <name> "..."`. Not stateless:
   the script replays the full prior conversation from
   `data/gemini_sessions/{name}.json` (gitignored) before each new turn, so
   Gemini keeps context across a multi-step jurisdiction investigation.
   Google Search grounding always on.
2. **Verification — always live, never trusted.** Every URL/agency-code/
   dataset-ID gets an actual probe (curl for simple reachability, Playwright
   when a real browser is needed). Freshness checked via real `MAX(date)`
   queries, never catalog metadata. When Gemini's specific guess is
   close-but-wrong, try plausible variants directly before looping back.
3. **Feedback loop.** If everything fails, write a `GEMINI_FEEDBACK_REPORT`
   (status overview, exact failure codes, what's being asked for) back into
   the *same* persistent session, so Gemini has the full trail of what's
   already ruled out. Can chain many rounds.
4. **Institutional memory — moved up from the former step 6.** Every batch
   — wins *and* dead ends — gets a `docs/ROADMAP.md` entry and a status
   line in `data/jurisdiction_health_matrix.json`, logged **immediately
   upon a lead being confirmed dead (step 2/3), not batched to the end** —
   if step 2 fails and the run is aborted, logging that only happens later
   in the sequence never executes for that failure. This is the first
   phase's actual output: a jurisdiction is either resolved to a live
   source, or logged as a dead end with evidence, before anything else
   happens.

### Phase II — Project Acquisition (the fork)

> **Changed 2026-08-05:** capture scripts write to GCS and touch the database
> ZERO times, while step 9 reads from `project_document_files` — so ~78% of the
> corpus was invisible downstream. Run `register-gcs-documents.py` after EVERY
> capture batch, and assert the next step can see this one's output.


Two mutually exclusive paths out of Phase I, both producing the same thing:
a standardized list of raw project candidates to hand to Phase III.

5. **Provider wiring** *(path A — a structured source was found)*.
   Confirmed sources get an existing provider (`Socrata`/`ArcGIS`/
   `Accela`/`EnerGov`/`CKAN`/`Carto`/`CSV`/`TdlrTabs` — 8 platform types
   as of 2026-07-28) or a new one if the platform is genuinely novel.
   Config goes into `scripts/state_agent_pipeline/core/state_configs.py`,
   dry-run first, then `--merge-state`.
6. **Direct project-level research fallback** *(path B — moved up from the
   former step 9; fires only when steps 1-4 find no structured source at
   all)* **— added 2026-07-31, for any state, not just Illinois.** A real
   and common outcome for smaller counties/cities with no digitized permit
   system at all (confirmed live for ~20 IL jurisdictions in one batch:
   DuPage/Lake resolved to false positives, McHenry/Kane/Will named the
   right platform but wrong exact URL, McLean/Rock Island/St. Clair are
   real sites with no online application system, Winnebago/Madison gave
   dead URLs). No pullable source doesn't mean no real commercial
   construction activity worth capturing — this path researches specific
   named projects directly instead of a feed:

   a. **Grounded research call.** One `google_search`-grounded Gemini
      call per county (or per project, for a deeper follow-up), asking
      for named projects with a fixed field set (name, address, type,
      cost + confidence level, SF/acreage, developer, contractor,
      architect, status, tenants, completion date, source citation) and
      an explicit instruction to write "Not identified in public
      records" rather than guess at any field it can't find. See
      response_mime_type caveat in step 1/Flash's docstring above
      (`scripts/research-county-sources.py`) -- the same
      google_search-corrupts-structured-output issue applies here, so
      this call must NOT set response_mime_type either. **Also ask for a
      per-project "pullable document" check as part of this same
      call** -- added 2026-07-31, per Asif's explicit ask ("make sure
      both projects and docs are captured, especially drawings"): the
      grounded call must separately state, per project, whether it can
      find an actual document (site plan PDF, PUD plan set, permit
      application, RFP, EIS report, drawing set) with a direct URL on
      the relevant municipal/county planning department's site -- not
      just a news article about the project. If none is findable, it
      must say "No pullable document found" explicitly rather than
      omitting the question. **A "pullable document" claim from this
      call is not itself verified** -- it still needs the same
      live-URL check as everything else (confirmed live on McLean
      County, IL: a first pass returned portal-level domains like
      `normalil.gov`/`illinois.gov` rather than exact document URLs --
      those domains being real is not the same as the specific document
      being reachable at a specific link). Do not treat a document as
      pulled until it has actually been fetched, the same discipline as
      step 8 below.
   b. **Independent cross-check (REQUIRED, not optional) -- this is the
      whole point of the step.** Every specific numeric or named-entity
      claim from (a) gets re-verified via a SEPARATE search call, not a
      second read of the same grounded response -- trusting one model's
      self-reported "High confidence" is exactly the failure mode this
      whole doc exists to prevent. Verified live 2026-07-31 across 8
      claims (DuPage + Cook County test batch): 6 fully confirmed
      (Block 59 $53M redevelopment cost, Joanne B. Wagner Community
      Center's $84.95M/Dewberry/McHugh+Nacional JV/fall 2027, Meadowbrook
      Shopping Center's $9.5M TIF cost, Amazon Oak Brook's 225,000 SF/27
      acres/Oct 2028, Obama Presidential Center's June 19 2026 opening,
      111 W. Monroe's developer/architect/contractor), but 1 real
      discrepancy caught (111 W. Monroe's hotel room count: Gemini
      claimed 308 keys, independent search found the real figure is 226)
      and 1 claim left unconfirmable (111 W. Monroe's $345.7M total
      project cost -- only the $40M+$50M TIF funding pieces are publicly
      documented, no total project figure exists in public sources).
      This ~75% clean/~25% needs-a-second-look rate is exactly why the
      cross-check is mandatory, not optional, and why nothing from (a)
      gets treated as fact until (b) confirms it.
   c. **Load path -- built and run 2026-07-31.**
      `scripts/load-research-fallback-projects.py` converts a findings
      file's projects into the corpus schema
      `load-corpus-to-postgres.py` already expects, with a hard safety
      rule: only projects with `cross_checked: true` AND a `CONFIRMED`
      result are included by default (`--include-unverified` is an
      explicit opt-out, not the default) -- a claim from (a) that
      never went through (b) does not meet the bar every other source
      in this corpus meets. project_id convention:
      `{state}-{county}-research-{slug}`, e.g.
      `il-kendall-research-cyrusone-c1-yorkville-data-center-campus`,
      so these stay visibly distinct from structured-source IDs.
      First real run: 8 of 21 total projects found across
      Kendall/McLean/Sangamon, IL met the cross-checked bar and are
      now loaded, verified live in `projects`. Run
      `compute-county-coverage.py` after loading, same as any other
      corpus change, so `/coverage` reflects the new rows.
7. **Data-quality gate / dedup — moved up from the former step 5.**
   `scripts/check-corpus-integrity.py` (+ CI on push/PR) checks for
   duplicate IDs across the whole corpus. Run **right after acquisition
   (step 5 or 6), before any of Phase III's expensive per-project work** —
   not just via CI on push after documents/enrichment have already been
   paid for. Clean structured sources route through `generic_mapping.py`'s
   no-LLM path instead of paying for Flash/Sonnet.

### Phase III — Project Processing & Enrichment

> **Changed 2026-08-04:** steps 8-10 are DOCUMENT-TYPE-BLIND. Step 2 must
> classify document TYPE; step 8 must rank **addenda > spec book > MEP drawings
> > rest**; step 9 must run spec-book extraction; step 10 must output spec
> POSITION (basis of design / listed alternate / absent).
>
> **Changed 2026-08-05, three defects in that plan:**
> 1. **Never apply a download cap on filename alone.** SAM.gov serves
>    `Attachment_A.pdf`, `Amd_1.pdf`. Inspect page 1 for `ADDENDUM NO.`,
>    `SECTION nn nn nn`, `BASIS OF DESIGN` first; cap after.
> 2. **Spec-book extraction is ADDITIVE, not an exclusive fork.** Page text for
>    everything (it feeds pgvector/FTS), PLUS MasterFormat extraction on any
>    document whose pages show spec structure — including addenda, which rewrite
>    whole sections.
> 3. **Spec position is COMPUTED, not read:**
>    `position = baseline(spec book) + overrides(substitution_rulings)`.
>    A manufacturer absent from the manual but approved by Addendum 02 must not
>    report as Absent. **Step 10 therefore JOINS step 11.**
>
> **Model routing:** step 9 and step 10 use **Pro**; triage inside step 10 stays
> on Flash. See Part 3.


Runs only on the new, deduplicated projects Phase II produced.

8. **Project-document pull (REQUIRED, not optional) — moved up from the
   former step 7.** For every new project, find and pull its real source
   documents (RFPs, board minutes, EIS reports, site plans) the same way —
   via Gemini (`gemini_discovery_chat.py`), live-verified before download,
   uploaded to `gs://specindex-ai-raw-documents/{state}/` (not git — large
   binaries). **GCS-only, no local intermediate copy** — Asif explicitly
   said (2026-07-28) documents should never be saved to a local folder,
   only to GCS; any future document-pull script should stream/upload
   directly, not stage through `data/documents/{state}/` first (the
   existing NJ script, `scripts/fetch-nj-documents.py`, downloads locally
   then needs a separate manual `gcloud storage rsync` — that's the *old*
   pattern, not the target one). Before assuming a source's documents are
   pullable (e.g. trusting an "Accela Attachments Tab" claim from a Gemini
   discovery response), verify live whether attachments are actually
   public without login — **confirmed live for Cleveland (COC) that they
   are not**: the Attachments tab UI loads for anonymous users, but it's
   an upload form, and the real backend call that would list existing
   documents (`.../Dpr/Handlers/Api.ashx/ab/records/{id}/planroom`)
   returns 403 Forbidden anonymously. Do not skip straight to building a
   downloader on an unverified claim, even one as specific-sounding as
   Gemini's was here. **First real win, same day:** SAM.gov's public
   opportunity API (`sam.gov/api/prod/opps/v3/opportunities/{noticeId}/
   resources`, then `.../resources/files/{resourceId}/download`)
   genuinely exposes real downloadable attachments (structural drawings,
   specs, bid abstracts) with zero auth — verified by actually
   downloading and file-type-checking a real PDF. Built
   `scripts/fetch-sam-gov-documents.py` (GCS-only, per Asif's instruction
   above), ran for all 44 GA SAM.gov projects: 30/44 had real documents,
   411 files, 752MB uploaded to `gs://specindex-ai-raw-documents/
   georgia/`. Document access genuinely varies by source type (federal
   solicitations are public by law; municipal permit attachments often
   aren't) — verify per source, never assume uniformly good or bad.
   **Remaining scope:** everything besides GA-SAM and the earlier NJ
   web-research work.
9. **Document text extraction — moved up from the former step 10, added
   2026-07-29.** For every document just pulled in step 8, extract real
   per-page text into `document_pages` (pgvector-ready, embedding column
   added but not yet populated) via
   `scripts/extract-document-text.py --document-file-id` (or `--batch
   --state --document-type`) — feeds step 10 below as its primary source,
   and is the foundation for the chat agent's retrieval and, later,
   structured material extraction. Native text (PyMuPDF) is tried first —
   free, instant, and most real documents in the corpus already carry an
   embedded text layer, including CAD-exported drawing sheets. Only pages
   with no meaningful native text (<20 chars) render to a one-page PDF
   and go to Google Document AI, chosen over a self-hosted OCR pool after
   a live head-to-head test (comparable accuracy, better layout-aware
   output, ~$360 total at the corpus's estimated ~240K OCR-needing pages
   vs. the engineering cost of running a CPU OCR worker pool). Automated
   via `.github/workflows/extract-document-text-pipeline.yml`, same WIF +
   Cloud SQL Auth Proxy pattern as every other pull-*.yml workflow.
10. **Project enrichment (REQUIRED, not optional) — moved down from the
    former step 8, added 2026-07-29.** Run
    `scripts/enrich-project-details.py <spx_id or slug>` (or `--batch
    --limit N` across many) to populate the AI-enriched detail-page
    sections — Executive Brief, CSI Scope Matrix, Verified Construction
    Team, Permits, Contacts — via the same two-pass search-grounded
    discovery + independent cross-check method used to build the first
    real page (`SPX-000157`, Hyundai-SK Battery Plant). **Should read step
    9's extracted document text as its primary source, using web search
    only to fill gaps or cross-check** — a project's own RFP/spec sheet is
    higher-fidelity than the open web for facts like architect or
    contractor; this reordering (previously enrichment ran before text
    extraction, forcing it to search the open web first) hasn't been
    re-implemented in `enrich-project-details.py` itself yet, only
    reflected here in step order — **real remaining scope**. Writes to
    `project_enrichment` (per-fact rows with `confidence`/`sources`) and
    `project_enrichment_checks` (a 30-day recheck cooldown, so a project
    that genuinely has nothing findable doesn't get re-queried/re-billed
    every run). This is what makes `components/ProjectDetailView.tsx` —
    **the adopted default template for every project page, see
    `docs/PROJECT_PAGE_REDESIGN.md`** — actually render its enriched
    sections instead of falling back to the raw description; a project
    without step 10 still gets a working page, just a thinner one. As of
    2026-07-29 only `SPX-000157` has been through this step; running it
    across the rest of the corpus is real remaining scope, same as
    step 8's GA-SAM/NJ-only coverage today.

### Phase IV — The Moat (step 11)

> **Changed 2026-08-05:** federal documents CANNOT deliver rulings. 400 pages of
> SAM.gov text containing "reject" produced ZERO named rulings — all boilerplate
> ("CONSULTANT RESERVES THE RIGHT TO REJECT ANY SYSTEM WHICH..."). Federal
> amendments carry basis-of-design and substitution PROCEDURES only.
>
> Rulings live on state/local portals, and only APPROVALS are public: AIA A701
> §3.3.4 requires a pre-bid approval to be set forth in an addendum, while
> rejections go privately to the requester. Local addenda are frequently
> SCANNED IMAGES, so OCR must be on or this step reads nothing.


Runs on rank-1 documents (addenda / amendments) produced by step 8, after
step 9 has extracted their text.

11. **Substitution ledger (REQUIRED wherever addenda exist) — added
    2026-08-04.** Steps 1-10 capture what was *specified*; nothing captures
    what was *contested*. This step does. Pre-bid substitution requests are
    ruled on publicly and the approved or rejected manufacturers are **named,
    with dates**, in addenda posted to public bid portals and in SAM.gov
    amendments. Extract, per addendum: the requesting party, the manufacturer
    and model proposed, the manufacturer it would displace, the ruling
    (approved / approved-as-noted / rejected), the date, and a page-level
    citation. Write to a dedicated substitution table keyed to the project.

    **Why this is the moat and not just another extraction.** It is the only
    public artifact that records *competitive displacement* — who was basis of
    design, who attacked the spec, and who won. No incumbent indexes it: Dodge
    SpecShare and ConstructConnect Analyze report that you were specified, at
    MasterFormat granularity, but neither is documented as reporting your
    POSITION or who displaced you. And on state/local portals **addenda come
    down after award**, so a competitor starting later cannot backfill it.
    Two years of this data is an asset that cannot be bought.

    **Sequencing.** SAM.gov RETAINS its amendments, so prove the extraction
    on the federal corpus first — free, permanent, already wired. The
    genuinely time-sensitive build is the **state/local addenda crawler**,
    because every week it is not running is data permanently lost. A crawler
    that only ARCHIVES the PDFs is enough to start the clock; extraction can
    follow against a growing archive.

    **Status 2026-08-04:** not built. ~14 amendments held, all from SAM.gov,
    captured incidentally rather than deliberately.

**Known real limits (be honest about these, don't oversell):** discovery
still needs a human+Claude verification loop per lead every time — not
unattended. New platform types cost real debugging time regardless of county
count. All 4 scheduled crons are disabled as of 2026-07-28 (Asif's explicit
request), so nothing refreshes automatically yet. Statewide sources like
TDLR are rare (1 of 49 states fully panned out on a first broad search) but
by far the highest-leverage target when found. Real CAPTCHA gates (Colorado
Springs' PPRBD) and login/invitation-only systems (Jacksonville's JaxEPICS,
El Paso County's EDARP) are hard stops — no anti-bot-evasion tooling,
regardless of legitimate purpose. asif-test's earlier national scan found
only ~0.3% of all US counties have a clean deterministic feed at all — full
"all counties" coverage isn't realistic through this method; national +
statewide + largest ~100-300 counties by population is the realistic
scalable target.

---

---

# Part 2 — Non-jurisdictional sources

Phase I assumes a jurisdiction. These sources are national and keyed by
document class, so they enter the loop at Phase III instead. Ranked by yield
per unit of effort.

| source | access | what it yields |
| :- | :- | :- |
| **SAM.gov** `opportunities/{id}/resources` | free, anonymous, no API key | **Full federal project manuals AND amendments.** Verified 2026-08-04: 187 files included `SpecsAsOne.pdf` (18.9 MB) and Amendments 0001-0005. Federal amendments ARE addenda, and SAM.gov RETAINS them. |
| **UFGS** (WBDG) | free, no login | Complete Divisions 21-28, quarterly, public domain |
| **VA TIL** | free `.docx`, predictable URLs, on data.gov | Entire master spec library |
| **Public university / state agency design standards** | free, permanent URLs | MasterFormat-numbered Div 23/26. Highest breadth-to-effort ratio in the entire set; nobody harvests it systematically |
| **State/local e-procurement portals** | mostly free registration | Project manuals **plus addenda** — the only time-sensitive source, since these vanish after award |

# Part 3 — Reference

## Goals and scope

**Data pull window.** Standing anchor is **2025-01-01, fixed** — not a rolling
lookback. Use `PULL_ANCHOR` / `--since-date`; never a hardcoded day-count, which
drifts every session it is reused.

**Coverage.** Maximise breadth AND depth for the top-500 US counties by
population (`docs/us_counties_by_population.md`, real Census data). A county
with structured data but no document path is a partial win. Paced in reviewed
batches of five.

**Documents are the moat, not permit-metadata breadth.** A discovery win
requires BOTH structured data and a real document path, even if gated. Pure
ArcGIS/Socrata bulk feeds are Shovels.ai's axis, not SpecIndex's.

**The wedge is basis-of-design attribution.** In Division 23/26 schedules the
engineer names a basis-of-design manufacturer, then adds "or equal". Basis of
design vs listed alternate vs absent is the highest-value fact, and no incumbent
is documented as distinguishing them. The buyer is the independent rep agency.

**The moat is the substitution ledger.** Approvals are published in addenda by
contractual requirement (AIA A701 §3.3.4); rejections are communicated privately.
Addenda come down after award, so a back-file cannot be reconstructed later.
Federal documents carry basis-of-design and substitution PROCEDURES but not
rulings — verified 2026-08-05, 400 pages of "reject" yielded zero named rulings,
all boilerplate.

## Source-specific behaviour

**Accela** had five stacked defects, all fixed 2026-08-04: dates were never ISO
(`.replace("/","-")` produced `01-05-2026`, invisible to every windowed query —
29,589 rows across 19 states); the date filter was never applied (a permit-type
postback wipes the inputs, and `page.fill()` APPENDS on masked pre-filled
fields); the watermark was a date string and a non-empty one made
`lookback_days` a no-op; the row loop aborted at the first out-of-window row;
and there was no date chunking. **Select the permit type FIRST, then set dates,
via `.value` + `input`/`change`/`blur` dispatch — never `fill()`.** Searches run
in 90-day windows; higher `max_pages` reaches further BACK, not further into the
window.

**Accela has two attachment UIs.** `lnkFileName` + `__doPostBack` is
downloadable; a `<span>` + `ViewDocumentDetails` is metadata-only and exposes no
download path. "Lists filenames" is not "serves documents".

**eTRAKiT is NOT viable** — a hard 50-record cap on every public search and no
date column. Do not build the provider despite 11 verified jurisdictions.

**EDMS** on big-county GIS carries asset photos, not construction documents. The
proven document sources are all MID-SIZE counties on Accela/EnerGov with ungated
attachments, or a separate EDMS (Snohomish, rank 72).

**SAM.gov** returns full federal project manuals and amendments, anonymously.
Amendments are retained, so federal addenda are not time-sensitive; state/local
are.

**VA PG-18-1** moved to `vatilms.va.gov` behind an Okta loop. Still available
anonymously at `wbdg.org/FFC/VA/VAASC/VA%20{section}.docx` — 36 of 52 Div 21-28
sections verified. `wbdg.org` returns a 1,359-byte bot-wall stub for ALL HTML,
so HTML enumeration silently yields nothing; `.docx` fetches are unaffected.

**Owner design standards** (universities, state agencies) name manufacturers as
campus standards — UW publishes a literal "Preferred manufacturers list". Four
crawler defects each returned a FALSE ZERO: same-host-only crawling (standards
often live on a sibling subdomain), requiring a six-digit MasterFormat number,
requiring any number at all (files are named "Mechanical.pdf" — infer the
division from the discipline), and BFS spending its page budget before reaching
the library.

## Routine checks after any corpus or config change

- `scripts/check-corpus-integrity.py` — duplicate ids
- `scripts/check-config-geography.py` — configs pulling a WIDER geography than
  their hardcoded county label (`generic_mapping` takes county as a fixed
  per-config value)
- `scripts/audit-county-coverage.py` — live vs corpus counts in parallel. Run
  this instead of spawning audit agents; five were killed by the watchdog doing
  what this does in 90 seconds.
- `scripts/register-gcs-documents.py` — after EVERY capture batch
- Watermarks live in `data/pipeline/nj-dca/state-{config-key}.json`. A non-zero
  `last_processed_id` makes `--lookback-days` a complete no-op.

## Commercial actions that are NOT the agent's to take

- **Pay the MasterFormat licence** ($699/yr, revenue-scaled since Feb 2026)
  before describing CSI-division indexing publicly. The EULA prohibits
  incorporating it into commercial software without written permission, and
  `extract-spec-book.py` classifies by MasterFormat section — live exposure for
  a rounding error. This is Asif's action, not an agent's, which is why it lives
  here rather than in CLAUDE.md.

---

# Part 4 — Measured facts with a shelf life

Recorded with dates because they will age. Re-measure before relying on them.

- **OCR: 98.4% of pages carry native text** (24,167 pages, 2026-08-03) — but
  that was measured on federal CAD/Word exports. **Local agency addenda are
  frequently scanned images**; one verified example had a 3-character text layer
  and OCR'd to 9,518.
- **The corpus crosses the wire twice** (2026-08-05): capture uploads to GCS,
  extraction downloads it back. Measured 66 KB/s public HTTPS vs 125 KB/s
  authenticated client. Parsing ~28,000 documents that way is 9-12 days. The
  cheap fix is parsing during capture; the structural fix is running extraction
  in-region.
- **Index growth will exceed cache at 1M pages.** GIN 0.7 GB + HNSW 1.5-2.0 GB
  against 2,481 MB `shared_buffers`. `maintenance_work_mem` (64 MB), NOT
  `work_mem`, governs GIN/HNSW builds.
- **Top-20 counties are structurally metadata-only** (2026-08-04): 14 of 20 have
  no per-record attachment endpoint and no EDMS. They need a new source, not
  another pull.

---

# Part 5 — Superseded: the original three-agent plan

Written 2026-07-26 as a pre-build plan, before the 11-step loop existed. All
three agents were built and still run:

- **Agent 1 (Quality)** — `scripts/compute-state-quality.py`
- **Agent 2 (Depth)** — `scripts/compute-county-coverage.py`
- **Agent 3 (Puller)** — the per-state pull workflows in `.github/workflows/`

The full 130-line plan was removed 2026-08-05. It described how the work was
organised before the loop, which is now only useful for understanding why
those three scripts are shaped as they are — and git holds it:

```
git show 6df74ed:docs/AGENT_STRATEGY.md
```

Kept as a pointer rather than 130 lines of dead text, because a strategy
document that carries its own obsolete history trains readers to skim.

---

## Document discovery: search the way a user searches (added 2026-08-06)

### The incident

Asif googled `1326 Saint Antoine St documents` and got a City of Detroit
Planning Commission staff report for a project whose SpecIndex record held **0
documents, 0 rulings, no owner, no architect, no GC**. The PDF names the
developer (Rock Economic Development Group), six storeys at 101'-6", 214,509
GSF, and the molecular-imaging / theragnostic / radiopharmacy programme — every
field the record renders as absent.

Nothing in this repo had ever fetched it. Nothing had ever looked: `grep -r
detroitmi` over the whole tree returned **zero hits**. Detroit reaches us
through one pipe, the BSEED permit ArcGIS layer, which is metadata and carries
no attachments.

The strategy was not wrong — `SPECINDEX_STRATEGY.md` already named council and
planning packets as the moat. **The crawler was never built.** The gap was
build, not insight.

### The two-part prompt (use this format verbatim)

```
Search google for:
1. project details for <project name> project in <city, state>
2. document links for me to download
```

Part 1 is never stored as fact. It exists to make the model resolve what the
project *is* before it hunts for files — and a resolved project produces better
file hits. Measured: it outperformed a documents-only query by hand.

Run on **`gemini-3.6-flash`**, not Pro. Flash is correct here under the standing
routing rule — *Flash where a verifier follows* — and a verifier does follow:
every URL is probed live before anything is stored. (`gemini-3.5-flash` returned
0 URLs on the control query; `gemini-2.5-flash` returned prose. Use 3.6.)

### Filenames are reliable; paths are not

This is the finding that makes the whole approach work, and the reason a naive
`url_resolves()` check throws away real documents.

Asked for the Detroit document, the model returned **five real filenames at five
wrong paths**. All 404. All became real PDFs after repair. Two independent
things go wrong, and both were observed on a single document:

| | model returned | actually live |
|---|---|---|
| directory | `/files/2025-04/` | `/files/events/2025-04/` |
| site root | `/sites/detroitmi.portal.gov/` | `/sites/detroitmi.localhost/` |

The marker segment sits **before** the date bucket, not after — a first
implementation appended it and repaired nothing. `find-project-documents.py`
probes both axes with HEAD, downloads only on a hit, and **caches the shape per
domain**, so one probe teaches the crawler that city's layout.

Acceptance is always content-checked: PDF magic number, and not byte-identical
to the host's known soft-404 body.

### Crawl beats search on economics — by roughly $17,000

Grounded search bills per query. 494,327 in-window projects hold zero documents.
But documents are published per **meeting**, not per project:

```
top   25 cities cover 80.5% of in-window zero-document projects
top  100 cities cover 90.3%
top  300 cities cover 96.6%
```

So `crawl-municipal-events.py` is the main line and search is the long-tail
fallback. One pass over a city's planning calendar captures staff reports for
every project it heard, at no per-project cost, and keeps working for projects
not yet ingested. Detroit sample: 6 event pages → 14 PDFs, all address-keyed
(`3000 Seminole`, `479 Willis`, `1914 Edison`) and therefore matchable.

**Known blocker:** 212,978 in-window zero-doc projects (43%) have a **blank
city** and state NY. City-based crawling cannot reach them until that is
relabelled — relabel, never delete.

### Per-state fleet

`scripts/run-state-document-agents.sh GA FL TX` (or `ALL`). One worker per
state, **background bash, not Agent-tool agents** — the agent runner kills a
subagent after 600s of no output and a state sweep is hours of deliberately
rate-limited probing. Each worker writes `logs/state-docs/<ST>.log` and a
sentinel on clean exit; wait on the sentinel, never `pgrep`.

Capture is deliberately **not** filtered by project match. A held document with
no project attached is an asset; a document never fetched is gone once the city
rotates its site.
