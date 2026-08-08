# Ingestion — quick reference

How a project and its documents get from a government portal into the record
page. Written 2026-08-07 from a full end-to-end run on Maine BGS #3820, which
surfaced three defects that had each been silently returning zero corpus-wide.

**Companion files:** `PIPELINE_CONSOLIDATED.md` (the merged S1–S8 model and the
seam history), `PORTAL_ADAPTER_CONTRACT.md` (the six adapter rules),
`AGENT_STRATEGY.md` (the 11 steps with incidents), `.claude/skills/spec-pull/`
(the runnable version).

---

## Two paths, not one

| | **Path A — permit feeds** | **Path B — portal spec documents** |
|---|---|---|
| what | jurisdiction permit/solicitation metadata | the actual bid documents |
| volume | ~597,000 projects | hundreds of projects, thousands of documents |
| carries documents | rarely | **always — this is the point** |
| code | provider adapters (Accela, ArcGIS, Socrata, EnerGov) → `--merge-state` → `data/states/*.json` | `portal_adapters/` → capture → load |
| is it the moat | no | **yes** |

Path A is breadth and competitors have more of it. **Path B is the product.**
Both are documented below; the nine numbered steps are Path B.

---

## Path A — permit and solicitation feeds

Produces the ~597,000-project corpus. Metadata-rich, document-poor. It exists so
a rep can find a job at all; Path B is what makes the job worth opening.

| # | step | code | writes |
|---|---|---|---|
| A1 | **Config** — one entry per jurisdiction: endpoint, provider type, field map, date field | `STATE_CONFIGS` | — |
| A2 | **Pull** — provider adapter queries the source with a server-side date filter | provider modules (Accela, ArcGIS, Socrata, EnerGov) | raw rows |
| A3 | **Map** — normalise to the corpus schema | `generic_mapping` | normalised rows |
| A4 | **Merge** — id-deduped merge into the state file | `--merge-state` | `data/states/*.json` |
| A5 | **Load** — state files into Postgres | `scripts/load-corpus-to-postgres.py` | `projects` |
| A6 | **Roll up** — national corpus, coverage and quality | `merge-national-corpus.py`, `compute-county-coverage.py`, `compute-state-quality.py` | coverage tables |

### The four rules that keep breaking here

- **Never point `--output` at `data/states/*.json`.** Those flags mean "write a
  new file", not "merge into it". State files are written only by `--merge-state`
  or an explicit id-deduped merge.
- **Never hand-roll date conversion — use `generic_mapping._iso_date()`.** A
  non-ISO date does not error. It sorts wrong and the row disappears from every
  windowed query while sitting in the corpus. **The diagnostic: total rows grow
  but in-window rows do not.**
- **The window is anchored at 2025-01-01** (`--since-date`). A county with
  thousands held and a few hundred in-window is a date bug until proven
  otherwise — never conclude "the source is thin" first.
- **A dead source still answers queries, returning 0 rows for everything.** Probe
  `1=1&returnCountOnly=true` periodically; a live count of 0 against a non-zero
  corpus count is the signature.

### Provider notes

| provider | watch for |
|---|---|
| **Accela** | had five stacked defects at once (date never ISO, filter never applied, date-string watermark, sort assumption, no chunking). Two different attachment UIs — capture handles the `lnkFileName` one; the `span + ViewDocumentDetails` variant silently yields 0 |
| **ArcGIS** | string date columns map to NO date; `--merge-state` will not repair existing rows |
| **EnerGov** | pick `SearchModule=Permit` to unhide Advanced search — took Lubbock from 0 to 1,937 in-window |
| **eTRAKiT** | **not viable.** Hard 50-record search cap and no date column. Do not build the provider |

---

## The ten steps

| # | step | code | writes | how to tell it worked |
|---|---|---|---|---|
| 1 | **Discover** — enumerate solicitations, return every `doc_urls` entry per project | `scripts/portal_adapters/*.py` → `discover()` | nothing (in-memory) | count links on one listing row in a browser; compare to `len(doc_urls)` |
| 2 | **Capture** — fetch each URL, content-check `%PDF`, `classify()` for spec format, store to GCS, stamp `doc_type` from the filename | `scripts/run-portal-capture.py` | GCS + `coverage/pull-log/pull-<ts>.csv` | rows with `status=downloaded` **and** a non-empty `gcs_path` |
| 3 | **Load** — read the pull logs; create projects from spec-confirmed rows; register **every** downloaded row as a document | `scripts/load-portal-projects.py` | `projects`, `project_document_files` | corpus count rises; `documents registered this run` > 0 |
| 4 | **Link** — move jurisdiction-scoped rows onto their project | `scripts/link-portal-documents-to-projects.py` | `project_document_files` | `project_documents.document_count` |
| 5 | **Extract** — native page text (98.4% of pages need no OCR) | registration scripts | `document_pages` | pages joinable **via `document_file_id`**, not only `reference_document_id` |
| 6 | **Classify** — CSI divisions per document | `scripts/classify-spec-documents.py` | `project_csi_divisions` | divisions with `project_sk IS NOT NULL` |
| 7 | **Ledger** — basis of design, alternates, "or equal" | `scripts/extract-spec-positions.py` | `substitution_rulings` | cited findings, each with a page number |
| 8 | **Score** — value (0-30, sanity-bounded) + recency (0-25) + spec position (0-45, reads step 7's `substitution_rulings` and step 3/4's `project_document_files`, **not** step 9's enrichment) | `scripts/compute-project-scores.py` | `project_scores` | non-`NULL` `score` on any project with cited findings; breakdown columns (`value_score`/`recency_score`/`position_score`) sum to `score` |
| 9 | **Enrich** — two-pass grounded search (discovery, then independent cross-check) | `scripts/enrich-project-details.py` | `project_enrichment` | fact count; `confirmed` vs `reported` |
| 10 | **Serve** | `api/main.py` `/v1/projects/{id}` | — | signed **in**; signed out returns a teaser |

**Step 8 got its scheduled workflow 2026-08-07** —
`compute-project-scores-pipeline.yml`, daily 10:00 UTC (same slot
`enrich-project-details-pipeline.yml` uses, though that one's own schedule is
still commented out from the 2026-07-28 repo-wide cron disable). Until this
ran, nothing in `.github/workflows/` executed `compute-project-scores.py`
except by hand, which is why most of the corpus — including reference
records used for design/QA work — showed an unpulled `--/100` score on the
project page. `scripts/compute-project-scores.py` also gained a
`--project-id` flag the same day, so a single project can be scored (upsert)
without truncating and rescoring the other ~600K rows, the way the
full-corpus default path does.

### Running it end to end for one project

```bash
python3 scripts/run-portal-capture.py --states Maine --max-docs 0 --checkpoint
python3 scripts/load-portal-projects.py
python3 scripts/link-portal-documents-to-projects.py
python3 scripts/extract-spec-positions.py --project-id me-portal-maine-vertical-3820
python3 scripts/compute-project-scores.py --database-url "$DSN"
python3 scripts/enrich-project-details.py <project_sk> --database-url "$DSN"
```

`enrich-project-details.py` takes the **`project_sk`**, not the `project_id`, and
defaults its DSN to localhost — pass `--database-url` explicitly.

---

## The adapters

**27 portal adapters**, all tier 1 (direct free PDFs, no login): **11 Vertical**
(state building/facilities — where CSI-division building-product specs live, and
what SpecIndex actually sells) and **16 DOT** (highway lettings — volume, but
roads-and-bridges specs). 4 need a browser for a JavaScript listing; 5 need real
browser headers to get past an edge block.

Every adapter is the same two functions — `discover()` returning
`{project_name, project_number, bid_date, doc_urls}` and `fetch(url)` returning
content-checked bytes. Contract and the six rules: `PORTAL_ADAPTER_CONTRACT.md`.

**Two document classes, two spec conventions.** Vertical portals use CSI
MasterFormat (divisions 00–49, "23 05 00", PART 1/2/3). DOT portals do not — they
use the state's own Standard Specifications numbering ("SECTION 100", supplemental
specs, Job Special Provisions). A MasterFormat-only test fails every DOT adapter;
`check-portal-adapters.py` carries a separate evidence arm for each.

**Bid Express is account-gated** — measured, no anonymous read path even for an
"info" account — so ~20 DOT states behind it are deprioritised. QuestCDN states
(ID, NV, WY) charge $15–42 per download: log and skip, never pay.

## Automation — what runs without anyone asking

All scheduling is **GitHub Actions cron**. There is no separate scheduler
service; the queue and workers are invoked by those crons. Times are UTC.

| schedule | workflow | what it does | path |
|---|---|---|---|
| **daily 03:00** | `pipeline-jobs-run.yml` | executes **`specindex-pull-portals`** (Cloud Run Job) — `run-capture-and-load.py`, every document on every tier-1 portal | **B — the moat** |
| on push to `pipeline/`, `scripts/` | `pipeline-jobs-deploy.yml` | builds the image, deploys 4 Cloud Run Jobs by digest | — |
| **every 30 min** | `continuous-crawl.yml` | `schedule-crawls.py` enqueues due work, `crawl-worker.py` drains it | B |
| every 30 min | `deploy-reconcile.yml` | catches merges that fired no deploy | — |
| daily 07:00 | `pull-nj-dca-pipeline.yml` | NJ DCA | A |
| daily 08:00 | `pull-nc-pipeline.yml` | NC ArcGIS | A |
| daily 09:00 | `pull-all-deterministic-sources.yml` | the deterministic feeds, then corpus load and rollup | A |
| daily 09:00 | `pull-ga-federal-pipeline.yml` | GA DRI + federal | A |
| daily 09:00 | `coverage-daily.yml` | county coverage + state quality | — |
| daily 10:00 | `enrich-project-details-pipeline.yml` | step 9 enrichment | B |
| daily 10:00 | `compute-project-scores-pipeline.yml` | step 8 scoring — see note above | — |
| daily 13:00 | `daily-gcp-spend.yml` | GCP spend report by email | — |
| weekly Mon 06:00 | `coverage-weekly.yml` | full coverage rebuild | — |
| weekly Mon 07:00 | `branch-hygiene.yml` | deletes merged branches, files an issue for no-PR branches holding unique files | — |
| **monthly, 1st 07:00** | `pull-state.yml` | the broad state pull | A |

### The crawler

`schedule-crawls.py` → **`work_queue`** (67 rows) → `crawl-worker.py`. Cadence is
volatility-driven — hot sources are revisited more often than cold ones — and
per-domain concurrency caps live in the queue, not in the callers. `vanished_at`
is what makes the moat queryable: a document that disappears from a portal is
still ours, and we know when it went.

Specialist crawlers: `crawl-addenda.py` (the change record) and
`crawl-municipal-events.py` (council/planning packets — the class that produced
the Detroit staff report a plain Google search found and we did not).

### Honest status, 2026-08-07

- **`continuous-crawl.yml` does fire** — three successful runs today (16:11,
  19:40, 22:07 UTC). An older note claiming it had never run is stale.
- **But each run takes 34–42 seconds**, which is not enough to be capturing much.
  Firing is verified; *doing work* is not. Check what the worker actually
  claimed and wrote before treating the crawler as covering a source.
- **Portal capture now runs in Cloud Run Jobs, on a cron** *(changed 2026-08-08
  00:25 UTC — this bullet previously read "not on any schedule; run by hand")*.
  `specindex-pull-portals` executes `run-capture-and-load.py` daily at 03:00 UTC
  via `pipeline-jobs-run.yml`, capturing every document on a project rather than
  stopping at the first confirmed spec book.

  Three things had to be true and none were: the deploy workflow had failed on
  **every** run (`--args "$@"` word-splitting, so gcloud parsed the script's
  flags as its own) and left no jobs at all; nothing ever *executed* the jobs
  even once deployed; and a Job's filesystem is ephemeral, so capture writing a
  pull log and exiting would have left the loader nothing to read.

  Verified by executing the job by hand rather than waiting for the cron: the
  container boots, reads its secrets, reaches Postgres over the Cloud SQL socket
  and starts `[scope] 27 adapters`.

- **Long ingestion no longer runs on the laptop** for portal capture. The Cloud
  SQL proxy died four times on 2026-08-07, every time from the machine sleeping,
  and each failure read as a database problem rather than as a laptop. Other
  ingestion still runs locally and is still exposed to this.

---

## The failure mode, stated once

**A step succeeds into a place nothing reads from.** Seven instances so far. None
errored. Each returned a clean, fast, plausible zero — and a zero reads as "the
data isn't there" rather than "the code didn't look."

Recent examples, all found on one project in one day:

- Pages written to `reference_documents`, read from `project_document_files`.
  **207 of 207 spec books** had zero joinable pages.
- Documents written to a fresh pull log, read from the **biggest** one, so a
  single-state capture could never load.
- `Settings.from_env()` raising on a required key nothing read, so step 7 had
  **never run once** and the ledger sat at 0 rows.
- Document class re-derived from `title`, which the loader sets to the project
  *number*, so the spec book was skipped.

### The eighth: a text layer that extracted "successfully" and is garbage

The seven above are all *data written where nothing reads it*. This one is
different, and the two diagnostics below **cannot detect it**.

A PDF with broken font dictionaries, a custom encoding, or a scan with no OCR
extracts without raising. `document_pages` fills with mojibake. Classification
finds no divisions, the ledger finds no manufacturers, and both return a clean
zero — *after* a plausible amount of time, so the elapsed-time check passes. The
run is recorded as a document that simply named nobody.

**Measured 2026-08-07** on a random 3,000-page sample: **4.1% suspect**, median
alphabetic ratio 0.75, median common-construction-word hits 49 per page. So this
is not the sweeping failure it could have been — but there is **no detector at
all** today, and 4.1% of pages silently producing "no manufacturers named" is a
direct hit on the moat.

**Fix:** a text-quality gate at step 5 — alphabetic-character ratio plus a hit
count for common construction English (`shall`, `section`, `contractor`,
`material`). Below threshold, mark the page for OCR instead of storing it as
readable text. Note the existing measurement that 98.4% of pages are native text
was about *whether text exists*, not whether it is **legible** — a different
question, and this is the gap between them.

### The two diagnostics

1. **Check elapsed time and input count before believing a zero.** *0 findings
   from 1 document in 0.6s* is a bug. *0 findings from 1 document in 80s* is a
   fact.
2. **Each stage's exit check must BE the next stage's entry query** — not a
   similar one. Every seam above was a stage verifying its own write in its own
   terms.

### And one rule about filters

**A spec-shaped filter discards the documents that are not spec-shaped.** It
appeared twice, one layer apart: a `break` after the first confirmed document in
capture, and `spec_format in ('CSI','DOT SS/SP')` in load. Both threw away every
addendum, drawing and bid tabulation — a one-page addendum has no CSI structure,
so a spec test can never accept it. Capture and registration keep everything;
only *project creation* requires a confirmed spec document.

---

## Simplification — what to remove, not add

The pipeline's problem is not missing capability. It is **too many places where
one thing is stored, named or decided twice**, and every seam has been a
disagreement between two of them. Simplification is therefore the same work as
correctness.

**1. One home per document.** `reference_documents` and `project_document_files`
both hold project-scoped material, and `document_pages` can hang off either — a
CHECK enforces one owner, so the join silently returns nothing when code guesses
wrong. That alone caused two failures in one day (207 spec books with no joinable
pages; then `enrich-from-cover-sheet.py` scoping on the pre-057 home and
reporting a clean zero). **Rule: project-scoped → `project_document_files`;
jurisdiction-wide standards → `reference_documents`. Nothing writes both.**

**2. One place that decides what a document is — with one legal override.**
`doc_type` is stamped from the filename at capture. Forbid re-deriving it from
**`title`**, which the loader sets to the project number — that is what silently
skipped the most valuable document on a project.

But do **not** forbid re-derivation from **content**. Procurement officers name
files badly, and `Project_3820_Final.pdf` could be anything; locking in a
filename guess forever is its own trap. So: filename is the default at capture,
**content-based classification may override it once text exists**, and the
override must be recorded rather than silently applied. *(Corrected after review
— the first version of this rule banned all downstream re-derivation and would
have frozen a low-fidelity guess.)*

**3. Keep the pull-log file handoff. Fix the watermark instead.**
*(This entry previously proposed the opposite — that capture should write
`project_document_files` directly and demote the pull log to an audit artifact.
That was wrong.)*

The file buys two things a direct write loses:

- **Decoupling from a hostile environment.** Government portals are slow and
  unstable, and so is our own database — the Cloud SQL proxy died four times on
  2026-08-07. A transient DB blip during a four-hour scrape would force us back
  to the portal.
- **Replayability.** When load logic has a bug — like the `spec_format` filter
  that dropped every addendum — a durable log means fixing the bug and re-running
  the load. With a direct write and the payload gone from memory, a load bug
  means re-fetching PDFs from sources that may have rotated, vanished, or (on
  QuestCDN) charge per download.

The defect was never the CSV. It was **reading the biggest log instead of the
unprocessed ones.** The fix is a processed-marker per log, not deleting the seam.

**4. Fetch and parse once; keep the database as the seam.**
*(Also corrected. This previously read "run classification and ledger extraction
off that single in-memory text", which conflates deterministic I/O with
probabilistic extraction.)*

Text extraction is deterministic, CPU-heavy, and needs to happen **once per PDF**
— its output belongs in `document_pages`. Ledger extraction is **probabilistic**,
and every prompt improvement means re-running it across the whole corpus. Couple
them in memory and a prompt change costs a full re-download and re-parse of every
document.

The concrete win here is not merging stages — it is that
`extract-spec-positions.py` currently **downloads the PDF from GCS and re-parses
it** instead of reading `document_pages`, which already holds the text. Point it
at the database. Same for classification.

**5. One vocabulary.** The 11 steps and the 4 stages described the same work
twice, and the *metrics* drifted from the *instructions* until stage 2's "% with
≥1 document" caused the runner to discard five of six documents.
`PIPELINE_CONSOLIDATED.md` now carries one S1–S8 list; retire the old numbering
in prose rather than maintaining a mapping.

**6. One name field, written by one thing.** Cover-sheet enrichment and the
loader both write `projects.name`, and the loader overwrote 70 enriched names
with bid numbers. Either the loader stops writing `name` after insert, or
enrichment output is stored where a bulk loader cannot reach it.

**What NOT to simplify:** the per-stage checkers, the before/after corpus counts,
and the "assert the next step can see it" endings. Those are the only reason any
of the above was ever found.

## Improvements needed, ranked

**~~1. Put portal capture on a schedule, in the cloud.~~ DONE 2026-08-08.**
Deployed as `specindex-pull-portals` and executing daily at 03:00 UTC. Kept here
rather than deleted, because the reason it was #1 still governs what comes next:
a data product cannot depend on someone remembering, and **the pipeline running
at all matters more than monitoring it**.

**2. Diagnose the stalled capture run — measured 2026-08-08 00:59 UTC.** The
verification execution `specindex-pull-portals-jf6w7` started 00:23, and this is
what it shows:

- **capture works.** 27 adapters scoped; `[20/20]` projects at ~38/min emitting
  rate and ETA, 2–7 documents each. Real work, not a 34-second no-op.
- **it went silent at 00:36:59** on `[20/20] ... ETA 0s` and produced **nothing
  for the next 22 minutes**, while Cloud Run still reported it running. 54 log
  lines total. The load step never logged at all.
- one adapter error: `[4/27] bonfire: discover failed`.

Silence at the hand-off from capture into load is failure-mode instance 8 again
— *"loader read the biggest pull log, not the new one; corpus moved +0"* —
except this run does not report a wrong number, it reports nothing. **A hang is
the one outcome that looks identical to work in progress.** Check whether load
is blocked on the Cloud SQL socket, whether a pull log reached
`gs://specindex-ai-raw-documents/pull-logs/` at all, and whether the corpus
moved; print counts either side.

The daily 03:00 UTC cron will reproduce this unattended and report success by
never finishing. That is exactly the trap `continuous-crawl.yml` sets — fires
reliably, finishes in 34 seconds, does nothing. **Firing is not working, and
neither is running.**

**2a. Bound the job's runtime and require a terminal `[verify]` line.** Nothing
above would have been noticed by a checker, because the job has no deadline and
no completion assertion — the only reason it surfaced is that a human looked at
`executions list`. Any run over ~30s already owes rate and ETA; a *job* owes a
final line stating projects / documents / addenda, and a timeout that fails
loudly instead of hanging quietly.

**2b. Send the verified outcomes back to Gemini.** Its review of the branch
hygiene workflow scored 1 of 3 on checkable claims — right that `head -20` under
`bash -e` + `pipefail` kills the producer with SIGPIPE (verified, rc=141), wrong
that squash-merge defeats a merge-base test, wrong that `fetch-depth` was unset.
Disproving the squash-merge claim is what produced the measurement that chose
the final design. Per CLAUDE.md §4 the return leg is not optional:
`scripts/gemini_feedback_loop.py`. Without it, it keeps asserting what has
already been disproven.

> **Correction, 2026-08-08: the `fetch-depth` claim was scored wrong and was
> actually RIGHT — in `deploy-reconcile.yml`, not the branch-hygiene workflow
> the review was aimed at.** That job's `actions/checkout@v4` specified only
> `ref: main` with no `fetch-depth`, so it took the default depth-1 shallow
> clone, and its `git merge-base --is-ancestor` check could never resolve
> history. It failed daily, flagging all 14 recently-merged PRs (#146–#159) as
> "commits never reached main" — every one a false positive, confirmed by
> running the same check locally against a full clone. A `2>/dev/null` on the
> merge-base call hid git's own "not a valid object name" and made the
> misconfiguration indistinguishable from a real finding. Both fixed
> (`fetch-depth: 0`, stderr no longer suppressed, and an explicit
> "cannot evaluate" branch that names a clone problem as a clone problem).
> **The lesson cuts both ways:** the return leg exists to correct Gemini, but a
> scorecard is itself a claim, and this one shipped a wrong "wrong" that then
> sat in the doc as settled while the real bug failed a workflow every day.
> Re-verify a disproof before recording it, especially one that closes off a
> correct lead.

**3. Build an end-to-end chain checker.** No test asserts that stage N+1 can read
stage N; that shape has failed seven times. Shape:
`scripts/check-ingestion-chain.py --project-id <id>`, running every stage and
failing loudly at the first whose output the next stage cannot see —
`check-portal-adapters.py` applied to the chain rather than to one stage. Add a
text-quality assertion so the eighth failure mode is covered too.

**3a. Emit `discovered_count` per project.** S5's own metric is "% of listed
attachments captured", and it cannot be computed: the pull log records only what
was fetched, never how many were offered.

**4. Require `project_number` on every discovered project.** 94 of 381 rows in
the 2026-08-07 Maine log carry an empty `project_id` and can never attach to
anything.

**5. Collapse the two document homes.** `reference_documents` and
`project_document_files` both hold project-scoped material. Migration 057 fixed
the *pages*; the loader still writes down both paths. Project-scoped →
`project_document_files`; jurisdiction-wide standards stay in
`reference_documents`.

**6. Gate ledger quality before anyone quotes ledger counts.** Three known
defects in the Alabama rows: case-variant duplicates (`RECTORSEAL` /
`Rectorseal` / `RectorSeal` as three rows), evidence quotes that do not contain
the manufacturer name, and division misattribution (Eaton and Square D tagged
Division 23 when they are electrical). The prompt already forbids the middle two
— assert them in code rather than asking the model twice.

**7. Drain the extraction backlog.** ~14,000 registered documents are still
unextracted, so their divisions and rulings do not exist yet.

**7a. Build the text-quality detector.** 4.1% of pages in a random 3,000-page
sample carry text that extracted without raising and is garbage. No detector
exists, so those pages return a silent "no manufacturers named" — a confident
zero that is a fact about our parse, not about the document. Gemini implied the
problem was pervasive; measuring put it at 4.1%. Real, smaller than claimed, and
still undetected.

**8. Move REMAINING ingestion off the laptop.** The Cloud SQL proxy died four times on
2026-08-07, every time from the machine sleeping — the failure reads as a
database problem and is not one. Cloud Run Jobs; PR #150 fixes the image.

---

## Gotchas that cost time

- **Signed out, the API returns a teaser** — no documents, no citations, no
  enrichment. Indistinguishable from an empty product. Check this before
  debugging data.
- **`doc_type` is decided from the FILENAME at capture time.** Never re-derive it
  downstream from `title`.
- **`has_documents` is a GENERATED column** and rejects explicit writes.
- **`project_document_files` is unique on `(project_sk, url)`**, not `url`.
- **`\b` does not fire next to `_`** — `_` is a word character, so `_DOC_MSP`
  survives `[_\-]+(DOC|MSP)\b`. Use `(?=[_\-]|$)`.
- **A decreasing corpus count is a stop-everything signal.** Print counts before
  and after anything corpus-touching.
