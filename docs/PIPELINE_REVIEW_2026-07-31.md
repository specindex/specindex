# External review: pipeline step ordering (Gemini 3.5 Flash, 2026-07-31)

Requested feedback on `docs/AGENT_STRATEGY.md`'s 10-step Agent-Per-State/
research pipeline (see that doc for the current step definitions) --
specifically whether any steps should move earlier or later in the sequence.
Full context sent (what SpecIndex is, why the pipeline exists, measured
reliability data from the DuPage/Cook live test, known open gaps) is
preserved in full below the response for reproducibility. **Not yet acted
on** -- this is the raw external feedback, recorded before any reordering
decision is made.

## Recommended reordering

Splits the pipeline into three phases instead of one linear sequence:

```
PHASE I -- Source Discovery
1. Discovery
2. Verification
3. Feedback loop
4. Institutional memory (moved up from step 6 -- log immediately on
   verification failure, not several steps later, so an aborted run
   still leaves a record)

PHASE II -- Project Acquisition (the fork)
5. Provider wiring (if a structured source was found)
6. Fallback research (moved up from step 9 -- it's what GENERATES the
   project list when no structured source exists, so it can't run after
   steps that assume a list already exists)
7. Data-quality gate / dedup (moved up from step 5 -- run before any
   expensive per-project processing, not after)

PHASE III -- Project Processing & Enrichment
8. Document pull
9. Document text extraction (moved up from step 10)
10. Project enrichment (moved down from step 8 -- now reads the
    extracted document text as its primary source, using web search
    only to fill gaps or cross-check, instead of searching the open web
    first for facts that may already be sitting in the downloaded RFP)
```

## Reasoning given for each move

- **Fallback research before enrichment/document-pull**: steps 7/8 (old
  numbering) assume a project list already exists. If a jurisdiction has
  no structured source, the fallback step is what produces that list in
  the first place -- it's a discovery step, not a post-processing one.
- **Enrichment after text extraction, not before**: the documents pulled
  in step 7/8 are the highest-fidelity source available. Running
  search-grounded enrichment before reading them forces the model to
  guess or search the open web for facts (architect, contractor, cost)
  that may already be written in plain text inside the project's own
  spec sheet or RFP.
- **Institutional memory logging moved earlier**: if verification (step
  2) fails and the run is aborted, logging that only happens 4 steps
  later never executes for that failure. Dead ends should be committed
  to the health-matrix file the moment they're confirmed dead, not
  batched to the end.
- **Data-quality gate/dedup moved earlier**: currently dedup happens via
  CI on push, i.e. after documents have already been pulled and OCR'd
  and enrichment has already run. Checking for an existing/duplicate
  project right after discovery avoids paying for all of that on a
  project already in the corpus.

## Other feedback given

- **On the step 8/9 cross-check design** (grounded search, then an
  independent re-verification pass before accepting any claim): called
  it good practice, but suggested adding a **deterministic anchor
  field** -- e.g. verifying a named contractor against a state
  licensing-board lookup instead of a second LLM search call. Cheaper
  and more reliable than search-vs-search for at least one fact per
  project.
- **On the wrong-URL-guessing failure mode** (the most common failure
  this session): three suggestions --
  1. Give the model a per-platform URL-pattern cheat sheet (few-shot
     examples of how Accela/Socrata/etc. URLs are actually structured)
     instead of letting it free-form guess.
  2. Forbid synthesized URLs entirely -- require every URL the model
     outputs to be copied from an actual search result's `formattedUrl`
     field, not generated from probability.
  3. Run deterministic Google-dork-style queries first (e.g.
     `site:.gov "powered by Accela" "permit"`,
     `site:.gov inurl:arcgis/rest/services "permit"`) and feed those
     real results into the model's context, so it *selects* a URL
     rather than *inventing* one.
- **On whether step 9's fallback-research output (verified facts, no
  live feed) is a good enough product for reps**: yes -- one verified
  large project is worth more to a rep than many unverified small
  residential permits. Two product recommendations:
  1. A visible **trust badge** distinguishing `[Verified Research]`
     from `[Official Permit Feed]` in the UI, so reps know which kind
     of confidence they're looking at.
  2. A **re-check cadence tied to project phase**, not a flat interval:
     30 days in Planning/Design (spec window still open), 14 days in
     Bidding (window closing), stop entirely once Under Construction
     (window closed).

## Open decision

Whether to actually implement this reordering in `AGENT_STRATEGY.md` --
it's a real structural change (especially moving dedup before enrichment
and doc-text-extraction before enrichment), not yet decided as of this
writing.

---

## Full context sent for this review (for reproducibility)

<details>
<summary>Click to expand</summary>

### What SpecIndex is
SpecIndex is a startup product for building-product manufacturer reps — it
indexes real commercial construction projects (office, industrial, retail,
mixed-use, data center, medical, hospitality) across all 50 US states,
sourced from permit portals, federal/state procurement, and public records,
so reps can find open projects in their category before the spec window
closes. Corpus is currently ~330K rows.

### The problem this pipeline solves
County/city-level building-permit data is wildly non-standardized in the
US — every jurisdiction may run a different platform (Socrata, ArcGIS,
Accela, EnerGov, CKAN, Carto, a flat CSV, or nothing digital at all).
There's no single national API. The only way to grow coverage is
jurisdiction-by-jurisdiction discovery, and LLM-assisted discovery is
necessary at this scale but is also the single biggest hallucination risk
in the whole system — a plausible-sounding fabricated URL, dataset ID, or
dollar figure looks identical to a real one until someone actually checks
it live.

### Hard data on reliability (from a live test the same day)
- Ran the fallback-research step for 2 counties (8 named-project claims
  total, real dollar figures/contractor names/dates).
- 6 of 8 fully confirmed via independent search.
- 1 confirmed real discrepancy: model claimed a "308-key hotel," verified
  reality is 226 rooms — for a project it otherwise got the
  developer/architect/contractor exactly right.
- 1 claim (a specific total project cost) was uncheckable — only partial
  TIF funding figures exist in public sources, no total was ever published
  anywhere.
- Separately: a structural JSON-generation bug was found — combining
  Gemini's `google_search` tool with forced JSON output
  (`response_mime_type="application/json"`) silently corrupts the model's
  output (returns garbage instead of raising an error). This had been
  silently breaking discovery for an unknown-but-nonzero number of past
  jurisdictions before being caught and fixed.
- Also found: the deterministic (non-LLM) search step's relevance filter
  only checks that a jurisdiction's name appears as a substring in a
  result's URL/title, with no topic check — let through a "Dog Parks" GIS
  layer for "DuPage County" and California's unrelated "Williamson Act"
  land-conservation dataset for "Williamson County, IL."

### Known open gaps at time of review
1. Step 9 (fallback research) has no load path yet — produces verified
   findings as text/files, not rows in the production database.
2. The relevance-filter substring bug hasn't been fixed yet, only
   documented.
3. Success rate at scale is genuinely low for smaller jurisdictions — in a
   real ~20-jurisdiction Illinois test batch, only 1-2 had an
   actually-reachable structured data source.
4. Cost/time tradeoff is unresolved — each jurisdiction currently needs a
   human (or Claude) in the loop, doesn't scale past a handful per working
   session today.

</details>

## Addendum: reviewed a proposed 500-county single-sweep prompt (Kimi/Moonshot AI, 2026-07-31)

A colleague-proposed prompt (via Kimi) asked for one continuous chat session
to research ~500 of the most commercially active US counties, extract
named projects with cost/contractor/architect/tenant facts, and emit a
JSON array per project -- no independent verification step, no load path,
"CONTINUE FROM [county]" if output limits are hit. The prompt wording
itself was solid (good field schema, a real "Not identified in public
records" instruction, sound source-priority ordering) but the *execution
plan* repeats the unattended-bulk-generation pattern already rejected
twice earlier this session (the "all 50 states, all 9 steps" and "all 102
IL counties" requests).

**Sent to Gemini for a second opinion, given the reliability data above.**
Verdict: **execution plan is unsound as proposed.** Concrete risks raised:

- **The accuracy math**: applying this session's measured ~1-in-8 error
  rate on numeric facts to a dataset of this size (~500 counties x ~4
  projects average = ~2,000 projects) implies roughly 250 projects with
  wrong cost/square-footage/capacity figures if published without
  verification -- enough to damage credibility once users spot obvious
  errors.
- **The "CONTINUE FROM" trap**: a single long-running chat session hits
  real, hard limits before 500 counties -- context-window degradation
  (the model starts forgetting its own system rules deep into a long
  session) and per-response output-token limits (a markdown table + JSON
  block per county will eventually truncate mid-JSON, silently corrupting
  the array). Not a hypothetical -- a structural failure mode of the
  single-session approach itself.
- **Search-tool bottlenecks**: LLM-integrated search tools are built for
  ad-hoc conversational queries, not systematic high-throughput research
  across 500 jurisdictions -- expect shallow, rate-limited searching that
  misses the primary-source municipal/county documents the prompt asks to
  prioritize, defaulting to whatever ranks first in a generic search.
- **No load path** (same gap as step 9 above) -- raw chat output requires
  manual copy/paste/validation, negating the speed advantage of using an
  LLM in the first place.

**Recommended restructuring** (aligns with and extends this doc's earlier
reordering discussion): move from one manual chat session to a
programmatic pipeline --
1. County-by-county (or small-batch) API calls, not one continuous
   session -- isolates failures, avoids context/token limits entirely.
2. Enforced structured output (JSON schema/tool-calling), not
   markdown-table-then-JSON.
3. Decouple search from extraction -- run a real search API first
   (e.g. targeted `site:.gov` queries), feed results into the model's
   context, then extract -- rather than letting the model free-search.
4. Automate the cross-check as its own programmatic pass per project
   (a second, independent call specifically targeting numeric facts),
   rather than a human doing it by hand -- this is the piece the
   proposed prompt skipped entirely, and the one this session's live
   test showed is load-bearing (it's what caught the 308-vs-226-room
   discrepancy).

**Not yet acted on** -- recorded for reference alongside the ordering
review above; both point toward the same underlying architecture (small
batches, structured output, mandatory automated cross-check) rather than
either a hand-run linear pipeline or an unattended bulk sweep.
