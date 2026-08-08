# Session log — blockers and learnings

**2026-08-06 → 2026-08-07.** Append new sessions below; do not rewrite history
here (`COMPLIANCE_BRIEF.md` §5 — this file is provenance too).

---

## Open blockers — need a human

| # | Blocker | Effect | Unblock |
|---|---|---|---|
| 1 | **GitHub Actions major outage**, entire session | Nothing deployed. PR #148 queued. Spec-citations panel, CORS fix and record template all built and invisible | Wait; auto-merge is armed |
| 2 | **Secret Manager API disabled** on `specindex-ai` | Cloud Run Jobs cannot deploy — `--set-secrets` fails | `gcloud services enable secretmanager.googleapis.com`, create 4 secrets, grant `secretAccessor` |
| 3 | **No Docker locally** | `pipeline/Dockerfile` has never been built; Playwright+chromium on slim is the likely failure | First CI run is the real test |
| 4 | **Counsel's §8 screening questions missing** | The only per-request compliance gate has no content | Draft sent for review in `BUILD_COMPLIANCE_BRIEF.md` |
| 5 | **11 Firebase/Xcode skills untracked** in `.claude/skills/` | Guard flags them every run | Commit, delete, or ignore |
| 6 | **`project-discovery-sources.csv` malformed** — 29 of 47 rows have 10 fields against a 9-field header | `url` reads as `"Seattle"`; A2/A5/A7/A8 all read this file | Fix at source in the handoff |

**Resolved during the session:** Anthropic credits exhausted (→ moved to Vertex
Gemini, all Anthropic paths removed and CI-enforced); GCS bucket unconfirmed
(→ `specindex-ai-raw-documents`); SAM.gov key "missing" (→ was in `.env` all
along — I asked before checking).

---

## The dominant failure mode: a step that succeeds into a place nothing reads

**Four instances in one session.** Each looked like success; each produced a
confident zero downstream.

| seam | symptom | reality |
|---|---|---|
| Adapters → index | Austin 2,000 records "pulled" | **0 rows** in `projects` |
| A3 capture → DB | 229 spec books in GCS | **0** visible to the classifier |
| Extraction → classifier | 269 docs flagged `structured_extraction_at` | **0** CSI divisions; a *different* script set the flag |
| Capture → registration | pull log written | nothing read it |

**Rule:** after any pipeline step, assert the NEXT step can see its output. Every
script written this session now ends with a read-back, and `db.py`'s
`stage_run()` existed for exactly this reason.

## Confident zeros — an empty result is not a finding without a control

Six times an empty or error result looked like a fact about the world and was a
fact about our query:

- `gcloud run jobs list` → empty. **Expired auth**, not "no jobs". Control: the
  same credential listed the service we knew existed.
- Secret Manager "MISSING" → **API disabled**, a 403 not an absence.
- Delaware portal → 245 bytes, **HTTP 200**. A WAF rejection reading as a
  document. Browser UA + Referer returned 9.3 MB.
- Arkansas vertical → host-wide 403 while `robots.txt` returns 200 and permits
  crawling.
- A stale-year filter discarded a **1,610-page state spec book** as "stale".
- Dallas logged as `dead link` — from an `AttributeError` **in our own code**.
  A live portal nearly written off.

**Rule:** content-check, never status-check. Baseline against a known-nonsense
request on the same host. Classify our own errors as *adapter error*, never as a
source blocker.

## Work that looks landed and isn't

- **Three branches with no PR.** `gh pr list` showed zero open while
  `feat/portal-adapters` sat 16 commits ahead. A branch with a merged PR that
  keeps receiving commits is invisible to every obvious check.
- **Merging one would have deleted #146** — 61 lines of `api/main.py` including
  the 409 fix and the spec-citations endpoint. The **two-dot** diff caught it;
  three-dot would not have.
- **Four gitignore collisions.** `/coverage` (Jest) ate the coverage plan;
  `.claude/` ate the skill; then `test-results/`; then `pull-log/`. `git add` on
  an ignored path adds nothing and commits clean.
- **A script was written, run, and swept away by `git stash -u`** before it was
  ever committed.

**Rule:** guards, not notes. A note went into `CLAUDE.md` after the *second*
collision and the third happened 20 minutes later.
`scripts/check-gitignore-collisions.py` now runs on every PR — and needed its own
fix, because scanning `.claude/worktrees/` turned 24 findings into 1,532 and
buried them. A check that cries wolf gets switched off.

## The checker is the definition of done, not the report

`check-portal-adapters.py` **failed the first reference adapter** — mine, written
against my own contract minutes earlier. It had scraped Missouri's landing page
(one unrelated PDF) instead of the sub-page holding 1,238 documents.

Then agents found **three defects in the checker itself**:

- It matched any three space-separated numbers, so it passed a **culvert
  fill-height table**, an **upside-down engineer's seal** (`2026-07-20` →
  `07 20 26`) and a **plan-sheet route map**.
- **MasterFormat is a *vertical* convention.** State DOTs number their own way
  (ADOT "Section 601", WSDOT "Divisions 1–9"), so the original test would have
  failed every DOT adapter regardless of quality — and read as "DOT portals hold
  no specifications".
- A 25-page read window produced false negatives: UDOT's first
  measurement/payment heading is on **page 55**.

One agent reported its own PASS as a false positive rather than bank it. That is
the behaviour the contract exists to produce.

## Source-table findings

- **Bid Express serves nothing anonymously.** GraphQL returns `FORBIDDEN`;
  every `/{domain}/lettings` 302s to login. Removes ~30 of 90 sources and
  demotes adapter A6.
- **Tier ratings are wrong in both directions.** Tier 2 was wrong 6 times in 11
  — the recurring shape is an *authorization-flavoured error for a
  non-authorization reason* (UDOT 403s "User is not authorized" on a malformed
  request; one query parameter fixes it). Tier 1 conflates *metadata* with
  *documents* — Iowa publishes solicitations while plans sit in a private plan
  room.
- **North Carolina:** registration gates **responding** to bids, not **reading**
  them.
- **A model's filenames are reliable; its paths are not.** Five real Detroit
  filenames at five wrong paths — all 404, all real after repair. `url_resolves()`
  alone scores 0-for-5 on a set that is 5-for-5.

## Cost

- **Crawl beats search by ~$17,000.** Grounded search bills per query; 494,327
  in-window document-less projects × ~$0.035. Documents are published per
  *meeting*, not per project — top 25 cities cover 80.5% of them.
- **Two meters:** Claude Code runs on the Max plan (prepaid); Vertex burns ~$25k
  GCP credits. The Anthropic API was a third bill, hit zero mid-run, and is now
  banned and CI-enforced.
- **Gemini does bulk, Claude Code does judgment.** Flash returned CSI division
  **"100"** from a DOT book on its first Vertex run — there is no division 100.
  A validator caught it. Gemini proposes at scale; Claude Code and live probing
  dispose.

## Infrastructure

**The database never dropped a connection.** Four jobs died with *"server closed
the connection unexpectedly"*; `pmset` shows repeated **Maintenance Sleep** and
**Dark Wake Thermal Emergency** across the same window, while Cloud SQL sat at
12 of 400 connections answering in 0.4s and the proxy had been up four days.
**The laptop was asleep.** Reconnect logic treats the symptom; `caffeinate` is
the stopgap; Cloud Run Jobs is the fix.

---

## Numbers at session end

| | |
|---|---|
| Projects | 597,078 (+5,460) |
| Documents | 23,091 (+229 portal spec books) |
| Extracted pages | 124,120 (+44,037) |
| **CSI divisions** | **448** (from 4) |
| Verified portal adapters | 23, across 19 states |
| Spec books in GCS | 229 · 1,993 MB |
| NYC projects relabelled | 209,978 |

Adapters shipped: **A1** Socrata (Austin, Seattle), **A2** ArcGIS (Denver,
Raleigh), **A3** 23 portal adapters, **A5** Accela (Dallas, King County).
Remaining: A4 SAM.gov (key verified working), A7, A8. A6 skipped by instruction.

---
---

# Session — 2026-08-07 (evening)

**Method that produced everything below: run all 11 steps on ONE project.**
Maine BGS #3820 (Maine State Prison Gatehouse, Warren ME). Three defects had
each been silently returning zero across the whole corpus and were invisible to
running one step across many projects.

## Open blockers — need a human

| # | Blocker | Effect | Unblock |
|---|---|---|---|
| 1 | **PRs #156, #157, #158 unmerged** | Cloud Run capture not deployed; seam fixes not on main | Merge in order **158 → 157 → 156** — #156's job runs #157's loader |
| 2 | **Cloud SQL proxy died 4× from laptop sleep** | Long ingestion cannot finish locally; each death reads as a DB failure | #156 moves it to Cloud Run Jobs |
| 3 | **Alabama ledger rows have quality defects** | Case-variant duplicates, quotes lacking the manufacturer, division misattribution | Ledger quality gates; **demo Maine, not Alabama** |
| 4 | **~14,000 documents unextracted** | Their divisions and rulings do not exist; 19 projects still named a bare identifier | Drain the backlog |
| 5 | **4.1% of pages have suspect text** | Silent "no manufacturers named" on unreadable pages; no detector exists | Text-quality gate at step 5 |
| 6 | **`logs/` (328K) untracked** | Noise in every `git status` | Add to `.gitignore` |

**Resolved this session:** blockers 2, 3 and 5 from the morning list (Secret
Manager enabled; the pipeline image built and PR #150 merged; the §8 screening
gate drafted, reviewed by Gemini and corrected by counsel).

## The dominant failure mode, instances 5–9

| # | seam | looked like | actually |
|---|---|---|---|
| 5 | Spec book → its own pages | 219 pages extracted | 0 joinable from the project — **207 of 207 books** |
| 6 | Config → step 11 | "ledger empty, need more addenda" | the step had **never run once**; `Settings.from_env()` raised on a required key nothing read |
| 7 | Capture → extractor | spec book present, skipped | class re-derived from `title`, which the loader sets to the project *number* |
| 8 | Capture → load | 404 documents captured | loader read the **biggest** pull log, not the new one; corpus moved +0 |
| 9 | Migration 057 → cover-sheet enrichment | "0 projects with document text" | my own migration moved the pages the scope query looked for |

**Instance 9 is the lesson.** Fixing a seam created a new one, in a script I did
not touch. A schema move must be followed by a grep for every reader of the old
column.

## Confident zeros — the clock is the tell

Defect 7 was caught **only because a run finished in 0.6 seconds**. The result
was indistinguishable from a real zero; the *duration* was not.

> **0 findings from 1 document in 0.6s is a bug. 0 findings from 1 document in
> 80s is a fact.** Check elapsed time and input count before believing any zero.

## Work that looks landed and isn't — a new variant

`ci/adapter-index-loader` had **PR #148 merged**, then two more commits pushed
to it afterwards, belonging to no PR. Worse, the working branch's ref had been
**reset backward** to a commit already in main, so `git log main..branch`
reported *nothing ahead* while nine commits of real work sat in the object
store.

> A branch can look merged, look empty, and still hold a day's work. Test for
> **files main lacks**, never commit counts.

## Findings that change strategy

**Rulings live in the base spec book, not in addenda.** Measured: 3820's
addendum is one page, 563 characters of native text, zero occurrences of
*substitution* / *or equal* / *approved* / *rejected* — a bid-date extension.
All 8 cited findings came from the 219-page spec book: Sika (div 03), Grainger
and McNICHOLS (div 05), Simpson Strong-Tie + USP with an explicit "or approved
equal" (div 06), Canam Mass Timber (div 06). Basis-of-design attribution is
present **at bid time**. Addenda still matter for the *change* signal — a
displaced manufacturer is only visible there — but expect a low hit rate.

**A metric that is satisfied by one document gets implemented as one document.**
Funnel stage 2 read "% with ≥1 document" and the runner carried a matching
`break`. Maine listed six documents per project; we kept one. Metric is now
captured-against-listed.

**A spec-shaped filter discards the documents that are not spec-shaped.** The
same mistake appeared at three layers: the `break` in capture, `spec_format in
('CSI','DOT SS/SP')` at load, and storage gated on the CSI test. A one-page
addendum has no CSI structure, so a spec test can never accept it.

## Gemini review — three of my own proposals reversed

Asked for disagreement rather than validation, and got it:

- **Keep the pull-log file handoff.** I had proposed capture write Postgres
  directly. Wrong: the file buys decoupling from unstable infrastructure and
  replayability when load logic has a bug — exactly what let the `spec_format`
  fix re-run without re-fetching 311 documents.
- **`doc_type` must stay content-overridable.** Banning all downstream
  re-derivation would freeze a low-fidelity filename guess. Only `title` is
  banned.
- **`document_pages` is the correct seam.** Coupling deterministic extraction to
  probabilistic LLM extraction means a prompt change costs a corpus-wide
  re-download.
- **An eighth failure mode:** a text layer that extracts without raising and is
  garbage. Gemini implied it was pervasive; **measured 4.1%** on a random
  3,000-page sample. Real, smaller than claimed, and undetected.

Verified outcomes returned via `gemini_feedback_loop.py`; ledger holds 18 claims.

## Numbers at session end

| | before | after |
|---|---|---|
| Substitution ledger | **0** | **123** |
| Maine documents | 28 | 78 (385 captured, pending load) |
| Addenda in corpus | 1 | 22 |
| Spec books with joinable pages | 0 of 207 | 206 of 207 |
| Portal projects named a bare identifier | 70 | 19 |
| Corpus | 597,284 | 597,369 |

**Capture storage, the headline fix:** 74 of 381 documents stored → **385 of
385**, with 68 addenda, 73 drawings and 34 bid tabs now kept.

