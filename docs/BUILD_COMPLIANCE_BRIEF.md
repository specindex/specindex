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

## §8 Development request screening — DRAFT, pending counsel

**Status: not yet approved.** §8 of the brief instructs *"before implementing a
material request, answer each screening question"* but the questions did not come
through — the section is a header and an instruction. Below is a candidate list
derived **strictly from the brief's own language**; every question cites the
clause it comes from. **Send to counsel to confirm, correct or replace. If they
supply wording, theirs governs and this section is deleted.**

Reviewed against the brief by Gemini (2026-08-07), which found four real defects
in the first draft. They are fixed here and recorded at the end, because the
corrections say more about the failure modes than the questions do.

### Why this gate matters more than the standing rules

Every other section is always-on or reactive. §8 is the only one operating at the
moment of building, per request — and the only thing that catches **drift**. "Add
a contractor filter", "let users export a prospect list", "show which competitor
is weakest here" are unremarkable alone; together they move the product from
manufacturer-facing specification intelligence toward contractor-facing lead
generation, which §3 puts in *Requires Legal Clearance*. No standing prohibition
sees that happening.

A dated answer per feature is also the contemporaneous evidence §5 asks for.

### A. Provenance of inputs *(§2, §4)*

**A1. State the source of the data, logic and requirements for this work.**
Give the public URL and access date for third-party or public-record inputs; or
state explicitly *"direct customer discovery"* or *"original design"* where that
is the origin. Not a yes/no — a recorded answer.

**A2.** Did any part originate from a former-employer system, account, export,
email, device or private communication? *(§4)*

**A3.** Does it require reconstructing a dataset, report, metric or conclusion
**from memory** rather than from a lawful source? *(§4)*

**A4.** Does it derive from a remembered internal roadmap, customer complaint,
pricing detail, performance metric, product gap or strategic priority? *(§3)*

A2–A4 stay separate on purpose. Merging them into one "does this comply?" tick
is what gets skimmed; the friction is the point.

**A5.** Are the transformation logic, extraction prompts and validation methods
documented in git? *(§4)*

**A6.** Can every contributor certify no third-party confidential information was
contributed? *(§4)*

### B. Who it serves *(§3, §6)*

**B1.** Who is the user? *(Manufacturers and rep agencies are permitted; a
contractor seeking project leads requires clearance.)* Answer with the user, not
yes/no.

**B2.** Does it closely resemble a ConstructConnect offering? *(§3)*

**B3.** Does shipping it involve outreach to, or targeting of, anyone on the
restricted-party register? *(§6)* — If the feature is generic (an export, an
email send), the answer is about **how it will be used**, and belongs with
whoever operates it.

### C. What it says *(§7)*

**C1.** Does any copy name ConstructConnect, compare capabilities, or imply
knowledge of its gaps, pricing, plans or priorities?

### D. Patents *(§3)*

**D1.** Is any part of this intended for a patent filing, or an ownership
representation covering a concept possibly conceived during employment?

### How to answer

- **A1 and B1 recorded**, and **A2, A3, A4, B2, B3, C1, D1 all "no"**, and A5/A6
  satisfied → proceed. Note it in the commit message; that is the dated record.
- **Any "yes"** → **stop and escalate per §9.** Do not redesign around it. A
  feature needing clearance is not one an engineer makes clearable.
- **Uncertain** → §12: preserve, pause, escalate.

### Two questions deliberately NOT in this gate

**Conception date.** §5 requires pre-2026-06-15 activity be "identified
accurately and escalated" — but an engineer taking a ticket cannot know when an
idea was conceived. It belongs at the **roadmap level**, asked of the founder when
a feature is first proposed, not per commit. Cutting it entirely would drop a §5
requirement; asking engineers would produce guesses.

**Commercial launch.** §3 restricts paid sales before 2027-06-15, but it
explicitly *permits building* billing systems. A build-time question is the wrong
instrument: **merging code should never itself enable paid sales.** That belongs
in release management — a flag controlled outside the merge — and if a routine
merge could flip it, the deploy pipeline is the defect, not the checklist.

### Defects found in the first draft, and why they mattered

1. **A1 originally demanded every input trace to a public URL.** That narrows the
   perimeter *beyond what counsel wrote* — §3 permits "direct customer
   discovery", which has no URL. Inventing a stricter standard than the brief is
   the worst failure mode for this document, because it looks like caution.
2. **"Does this serve manufacturers or contractors?"** was compound, so answering
   "yes, manufacturers" tripped the stop rule and halted permitted work.
3. **A product rule was smuggled in as a legal one** — a claims-scope rule that
   appears nowhere in the brief. It is a good rule and it lives elsewhere; mixing
   the two blurs which is binding.
4. **Patent filings, documented transformation logic and contributor
   certification** were all missing, though §3 and §4 require each.

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
