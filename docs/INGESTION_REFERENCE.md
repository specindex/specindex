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

## The nine steps

| # | step | code | writes | how to tell it worked |
|---|---|---|---|---|
| 1 | **Discover** — enumerate solicitations, return every `doc_urls` entry per project | `scripts/portal_adapters/*.py` → `discover()` | nothing (in-memory) | count links on one listing row in a browser; compare to `len(doc_urls)` |
| 2 | **Capture** — fetch each URL, content-check `%PDF`, `classify()` for spec format, store to GCS, stamp `doc_type` from the filename | `scripts/run-portal-capture.py` | GCS + `coverage/pull-log/pull-<ts>.csv` | rows with `status=downloaded` **and** a non-empty `gcs_path` |
| 3 | **Load** — read the pull logs; create projects from spec-confirmed rows; register **every** downloaded row as a document | `scripts/load-portal-projects.py` | `projects`, `project_document_files` | corpus count rises; `documents registered this run` > 0 |
| 4 | **Link** — move jurisdiction-scoped rows onto their project | `scripts/link-portal-documents-to-projects.py` | `project_document_files` | `project_documents.document_count` |
| 5 | **Extract** — native page text (98.4% of pages need no OCR) | registration scripts | `document_pages` | pages joinable **via `document_file_id`**, not only `reference_document_id` |
| 6 | **Classify** — CSI divisions per document | `scripts/classify-spec-documents.py` | `project_csi_divisions` | divisions with `project_sk IS NOT NULL` |
| 7 | **Ledger** — basis of design, alternates, "or equal" | `scripts/extract-spec-positions.py` | `substitution_rulings` | cited findings, each with a page number |
| 8 | **Enrich** — two-pass grounded search (discovery, then independent cross-check) | `scripts/enrich-project-details.py` | `project_enrichment` | fact count; `confirmed` vs `reported` |
| 9 | **Serve** | `api/main.py` `/v1/projects/{id}` | — | signed **in**; signed out returns a teaser |

### Running it end to end for one project

```bash
python3 scripts/run-portal-capture.py --states Maine --max-docs 0 --checkpoint
python3 scripts/load-portal-projects.py
python3 scripts/link-portal-documents-to-projects.py
python3 scripts/extract-spec-positions.py --project-id me-portal-maine-vertical-3820
python3 scripts/enrich-project-details.py <project_sk> --database-url "$DSN"
```

`enrich-project-details.py` takes the **`project_sk`**, not the `project_id`, and
defaults its DSN to localhost — pass `--database-url` explicitly.

---

## Automation — what runs without anyone asking

All scheduling is **GitHub Actions cron**. There is no separate scheduler
service; the queue and workers are invoked by those crons. Times are UTC.

| schedule | workflow | what it does | path |
|---|---|---|---|
| **every 30 min** | `continuous-crawl.yml` | `schedule-crawls.py` enqueues due work, `crawl-worker.py` drains it | B |
| every 30 min | `deploy-reconcile.yml` | catches merges that fired no deploy | — |
| daily 07:00 | `pull-nj-dca-pipeline.yml` | NJ DCA | A |
| daily 08:00 | `pull-nc-pipeline.yml` | NC ArcGIS | A |
| daily 09:00 | `pull-all-deterministic-sources.yml` | the deterministic feeds, then corpus load and rollup | A |
| daily 09:00 | `pull-ga-federal-pipeline.yml` | GA DRI + federal | A |
| daily 09:00 | `coverage-daily.yml` | county coverage + state quality | — |
| daily 10:00 | `enrich-project-details-pipeline.yml` | step 8 enrichment | B |
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
- **Portal capture (step 2) is not on any schedule.** It is run by hand. Given
  the capture fix landed today — every document stored, not only spec books —
  every previously captured portal needs a re-run, and then this belongs on a
  cron.
- **Long ingestion should not run on the laptop.** The Cloud SQL proxy died four
  times on 2026-08-07, every time from the machine sleeping, and the failure
  reads as a database problem. Cloud Run Jobs; PR #150 fixes the image.

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

## Improvements needed, ranked

**1. Build an end-to-end chain checker.** No test asserts that stage N+1 can read
stage N. This is the single highest-value fix and would have caught all seven
seams. Shape: `scripts/check-ingestion-chain.py --project-id <id>`, running every
stage and failing loudly at the first whose output the next stage cannot see —
`check-portal-adapters.py` applied to the chain rather than to one stage.

**2. Emit `discovered_count` per project.** S5's own metric is "% of listed
attachments captured", and it cannot be computed: the pull log records only what
was fetched, never how many were offered.

**3. Require `project_number` on every discovered project.** 94 of 381 rows in
the 2026-08-07 Maine log carry an empty `project_id` and can never attach to
anything.

**4. Collapse the two document homes.** `reference_documents` and
`project_document_files` both hold project-scoped material. Migration 057 fixed
the *pages*; the loader still writes down both paths. Project-scoped →
`project_document_files`; jurisdiction-wide standards stay in
`reference_documents`.

**5. Gate ledger quality before anyone quotes ledger counts.** Three known
defects in the Alabama rows: case-variant duplicates (`RECTORSEAL` /
`Rectorseal` / `RectorSeal` as three rows), evidence quotes that do not contain
the manufacturer name, and division misattribution (Eaton and Square D tagged
Division 23 when they are electrical). The prompt already forbids the middle two
— assert them in code rather than asking the model twice.

**6. Drain the extraction backlog.** ~14,000 registered documents are still
unextracted, so their divisions and rulings do not exist yet.

**7. Move long ingestion off the laptop.** The Cloud SQL proxy died four times on
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
