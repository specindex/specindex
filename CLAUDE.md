# SpecIndex — operating rules

This file is auto-loaded into context on EVERY session. It carries only rules
that must be known BEFORE acting. Anything explanatory, historical, or
domain-specific belongs in `docs/AGENT_STRATEGY.md`, which is read on demand.

Each rule below exists because it was violated and cost real data or hours. The
incident is recorded in `docs/AGENT_STRATEGY.md`; only the directive is here.

---

## 1. Destructive guardrails

- **NEVER point `--output` / `--out` at `data/states/*.json`.** These flags mean
  "write a new file", not "merge into it". State files are written ONLY by the
  pipeline's `--merge-state` or an explicit id-deduped merge. Before running any
  unfamiliar script, grep it for `write_text` / `json.dump`.
- **A DECREASING corpus count is a stop-everything signal.** Print counts before
  and after any corpus-touching operation. If a rebuild reports fewer projects
  than the last run: do not commit, do not push, restore from git, diagnose.
- **Never delete a mislabelled row — relabel it.** The true jurisdiction is
  usually derivable from data already held. Relabelling is reversible.
- **`git show <commit>:<file>` returns the LFS pointer, not the data.** Use
  `git checkout <commit> -- <file>` to inspect or restore real content.
- **Confirm before merging a PR whose branch is far behind.** Read the two-dot
  diff (`git diff main <branch>`), not the three-dot. Four PRs on 2026-08-05
  looked like small additions and were reversions of newer work.

## 2. Data integrity — every failure here returns a plausible number, not an error

- **Never hand-roll date conversion.** Use `generic_mapping._iso_date()`. A
  non-ISO date does not error — it sorts wrong and the row vanishes from every
  windowed query while sitting in the corpus.
- **THE DIAGNOSTIC: total rows grow but in-window rows do not.** That divergence
  means a date bug. A county with thousands held and a few hundred in-window is
  a date bug until proven otherwise — never conclude "the source is thin" first.
- **A broken filter returns MORE rows, so a row count can NEVER validate a fix.**
  Read the control back after setting it. Check the distribution across windows,
  not the total. Compare two different filter values — identical results mean the
  filter is inert.
- **Baseline every endpoint probe against a nonsense path on the same host.**
  Government and .edu hosts answer unknown paths with HTTP 200 and their landing
  page. Require a product-specific signature AND a body that differs from the
  baseline. A generic word like "document" is not a signature.
- **URL-resolves is NOT verification — check the CONTENT.** A fabricated URL
  fails a link check instantly; a real URL with fabricated contents passes every
  check and fails only when the document is opened.
- **A dead source still answers queries, returning 0 rows for everything.** Query
  `1=1&returnCountOnly=true` periodically. A live count of 0 against a non-zero
  corpus count is the signature.
- **Verify a value's PLAUSIBILITY, not just its presence.** Sanity-bound numbers
  before ranking on them: Miami-Dade reports $7.86B for a beauty-salon
  alteration. Never quote Florida project values.
- **After any pipeline step, assert the NEXT step can see its output.** A step
  that succeeds into a place nothing reads from is indistinguishable from a step
  that ran.

## 3. Tooling invariants

- **Wait on a sentinel the producer writes, never `pgrep` a process pattern.**
  `while pgrep -f "<pattern>"` deadlocks when the pattern appears in the waiting
  script's own argv. Bound every wait loop with a counter so a missed sentinel
  times out loudly.
- **If CPU time balloons past a sane estimate with no progress output, kill and
  reroute.** Check `ps aux` CPU time, not wall clock. Any loop over ~30s must
  emit rate and ETA.
- **Use the service-account key for GCS, never user ADC.** ADC expires and the
  failure reads as "this source has no documents". Test with an object-level
  probe (`bucket.blob(...).exists()`), never `bucket.exists()`.
- **Parallelise small probes; cap large transfers at ~3.** Measured uplink
  saturates there — 8 concurrent transfers produced 0 uploads and OSError 65.
- **Rate-limit public government servers. A ban is permanent loss of a source.**
  Per-domain concurrency caps are enforced in `work_queue`; do not bypass them.
- **Use Playwright for gated or SPA portals** before concluding "no viable
  source". curl cannot see through an Angular shell.
- **Run `scripts/verify-environment.py` when anything returns unexpectedly
  little.** It checks credentials, IAM roles and config in ten seconds.

## 4. Working with Gemini

- **Gemini PROPOSES; live probing DISPOSES.** Measured accuracy on factual
  claims: 2 of 10. It is strong on systems reasoning and unreliable on any
  specific fact about the world. Never record a candidate it supplies without
  verifying it live.
- **Consult it at every wall** — a dead source, a gated portal, a bottleneck —
  before concluding a lead is dead.
- **ALWAYS send the verified outcome back, automatically.** Every consultation
  ends with feedback via `scripts/gemini_feedback_loop.py`. Without the return
  leg it keeps asserting what has already been disproven.
- **Never accept your own numbers back in stronger form.** Given "400 pages", it
  replied "14,000 documents" and used it to declare a strategy dead.

## 5. Cost and scope

- **Targeted file scoping.** Only inspect files named in the prompt or their
  direct dependencies. No repo-wide sweeps unless asked.
- **Concise output.** Diffs or the modified function, never full-file reprints.
- **Flag `/compact` at ~15 user messages or ~70% context.**

## 6. Product and legal constraints — do not violate

These stay in the execution file because this agent DOES write customer-facing
copy: on 2026-08-05 it edited the projects headline and the trust line, and it
writes PR bodies and Drive documents. A rule about what may be claimed is an
execution rule for anyone who writes claims.

- **Never scrape ConstructConnect, Dodge, Blue Book or BuildingConnected.** Their
  AUP forbids it, and the founder is ex-ConstructConnect. Public data only.
- **No cross-filtering chart dashboard, and NEVER a permit job-cost histogram**
  (iSqFt patents; US 9,633,012 does not require interactivity). Lead with alerts,
  digests and API.
- **Do not lead with project volume.** Competitors claim more. Sell spec position
  and citations.
- **Never state a claim wider than the evidence.** "No manufacturer named in the
  N documents we hold" — never "none named".
- **Do not claim brand-vs-competitor visibility.** 166 of 591,618 projects carry
  any brand mention, and those are tenants, not manufacturers.

---

## Read on demand — `docs/AGENT_STRATEGY.md`

- **The 11-step process** and why a jurisdiction is NOT done at step 5
- **Model routing** — which steps use Flash vs Pro, and why
- **Continuous crawling** — volatility-driven cadence, the queue, the workers
- **Data pull window** — the fixed 2025-01-01 anchor and `--since-date`
- **Coverage goals and the moat thesis** — what counts as a win
- **Source-specific behaviour** — Accela, EnerGov, ArcGIS, SAM.gov, EDMS
- **Incident history** — the failures behind every rule above
