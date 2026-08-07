# Build-time compliance — how the brief applies in this repo

**Companion to `docs/COMPLIANCE_BRIEF.md`, which is authoritative.** This file
adds nothing legal; it maps §2, §4, §5 and §7 onto concrete practice for anyone
— human or agent — writing code and copy here. Where the two differ, the brief
governs. Effective through **June 15, 2027**.

---

## §4 Clean room — what the pipeline must record

The brief requires *"the exact public URL, access date, source owner, license or
access terms, and retrieval method for each source"*. In this repo that is not
paperwork, it is a schema constraint:

| requirement | where it lives |
|---|---|
| public URL | `source_url` on every project and document row |
| access date | `fetched_at` / `fetch_date` (also GCS object metadata) |
| retrieval method | the adapter name in `coverage/pull-log/*.csv` |
| immutable retrieval log | pull logs are **append-only**, one file per run, committed |
| raw separate from processed | documents in GCS; extractions in Postgres, keyed back |
| transformation logic | adapters and prompts are in git, with the reasoning in commits |

**A row without a source URL and fetch date is a compliance defect, not just a
data-quality one.** The loaders already reject rows with no `project_id`; treat
a missing citation the same way.

**Blocked sources are logged, never worked around.** `registration required`,
`dead link`, `needs browser`, `no active solicitations` are correct outcomes.
This matters twice over now: it is good engineering *and* it is the audit trail
showing we stopped at every wall.

**Quarantine, do not delete.** If a source turns out to be questionable,
preserve it and escalate (§4, §9). Deleting is the wrong instinct.

## §5 Provenance — git history IS the evidence

- **Never rewrite published history.** No force-push over `main`, no rebasing
  published commits, no squashing that destroys authorship or dates.
- **Never backdate** a commit, document or file timestamp.
- **Preserve prior versions** when language is corrected. Change it forward as
  an ordinary update; the old version stays in history (§5, §9).
- Commit messages explaining *why* a thing was built are contemporaneous
  evidence of independent creation. Keep writing them.

## §7 Language — applies to every customer-facing surface

Site copy, PRDs, decks, PR bodies, Drive documents, marketing.

**Never write, imply or hint** that the idea came from ConstructConnect, that
SpecIndex counters or replaces it, that we know its gaps, pricing, roadmap or
priorities, or that we exploit anything learned confidentially.

**Approved framing** is in §7 of the brief. Use it as written.

Existing product rules point the same way and still apply:

- Do not lead with project volume — sell spec position and citations.
- Never state a claim wider than the evidence: *"no manufacturer named in the N
  documents we hold"*, never *"none named"*.
- Do not claim brand-vs-competitor visibility.
- No cross-filtering chart dashboard; never a permit job-cost histogram (iSqFt,
  US 9,633,012). One-directional citation only (Buildsite, US 12,242,990).
- Never scrape ConstructConnect, Dodge, Blue Book or BuildingConnected — their
  AUP forbids it independently of any employment question.

## §3 Perimeter — what to build

**Build:** manufacturer-facing specification intelligence — spec position,
basis-of-design attribution, substitution visibility, source-linked records.
Infrastructure, auth, billing, ingestion and QC are unrestricted provided no
former-employer material is used.

**Needs clearance first:** paid sales or commercial launch before 2027-06-15;
contractor-facing lead generation; outreach to restricted parties; anything
resembling a remembered internal roadmap; hiring from ConstructConnect;
comparison content naming it; patent filings.

The manufacturer wedge is the strategy on its own merits and predates this
brief. That it is also the defensible perimeter is convenient, not the reason.

## §9 Stop and escalate

Halt and raise it if: a source turns out to be ConstructConnect/Dodge/Blue
Book/BuildingConnected content however reached; a contact may be a restricted
party; a feature resembles something known from inside; anyone proposes
deleting, editing or backdating historical material; or a document cannot be
traced to a public URL.

## For agents working in this repo

Before adding a data source, re-read §4 above. Before writing customer-facing
copy, re-read §7. If a source is ambiguous, **log it as a blocker and stop** —
do not route around it. That is already how the pipeline behaves; now it is also
why.
