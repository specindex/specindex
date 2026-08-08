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
