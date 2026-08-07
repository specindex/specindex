# Build-time compliance — operational mapping

**Revision 2 — screening questions clarified; pending counsel approval.**

Companion to `docs/COMPLIANCE_BRIEF.md`, which is authoritative. This file adds
no legal judgment and confers no permission; it maps the brief onto engineering
practice in this repo. Where the two differ, the brief governs. Nothing here is
approved.

> **Heightened restrictive-covenant controls apply at least through
> June 15, 2027. Certain confidentiality, trade-secret, IP, preservation,
> remedial, and possible tolling obligations may continue beyond that date.**

---

## Development direction — no activity is categorically permitted

**Potentially lower-risk development direction, subject to legal clearance.**
Development activity is **not** categorically permitted merely because it is
private, unpaid, infrastructure-focused, or manufacturer-facing. The covenant
restricts providing, supervising or managing similar services for a competing
business during the restricted period; it does not require revenue, customers or
a public launch for that to apply.

Potentially lower-risk, still subject to clearance:

- Manufacturer-focused specification and brand intelligence
- Public permit, procurement, bid, announcement and specification sources
  obtained lawfully
- Source-linked project records and public citations
- Infrastructure, security, authentication, billing, ingestion and quality
  control developed without former-employer materials

Requiring clearance before proceeding — see §3 of the brief in full:
commercial launch or paid sales; contractor-facing project-lead products or
features closely resembling ConstructConnect offerings; outreach to restricted
parties; features derived from remembered internal information; hiring from
ConstructConnect; comparison content; patent filings.

## Source provenance — mandatory fields per source

The brief §4 requires the exact public URL, access date, source owner, license
or access terms, and retrieval method. The full mandatory schema:

| field | status | where it lives today |
|---|---|---|
| public URL | required | `source_url` on project and document rows |
| access date | required | `fetched_at` / `fetch_date`, GCS object metadata |
| **source owner** | required | **gap — not yet a column** |
| **applicable terms or license** | required | **gap** |
| **access authorization** | required | **gap** |
| **whether authentication was used** | required | **gap — adapters never authenticate, but this must be recorded, not inferred** |
| **data classification** | required | **gap** |
| **retention restrictions** | required | **gap** |
| **hash / immutable identifier** | required | `content_sha256` on documents; **absent on project rows** |
| retrieval method | required | adapter name in `coverage/pull-log/*.csv` |
| immutable retrieval log | required | pull logs append-only, one file per run |
| raw separate from processed | required | documents in GCS; extractions in Postgres, keyed back |
| transformation logic, prompts, validation | required | adapters and prompts in git |
| contributor certification | required | **gap — not yet collected** |

**The gaps are real and unclosed.** A row missing a required field is a
compliance defect, not only a data-quality one.

**Customer discovery is not automatically permissible.** It may be used only
after confirming the participant is not a covered customer, prospect or key
relationship, and recording that determination.

**Blocked sources are logged, never worked around.** `registration required`,
`dead link`, `needs browser` are correct outcomes.

**Questionable material: preserve without reviewing, copying, processing or
distributing it further.** Isolate it in access-controlled legal-hold storage,
preserve metadata, and escalate immediately. **Do not commit the material or its
substance to the ordinary repository.**

## Provenance record — repository history is one component

Repository history is **one component** of the provenance record and must be
supplemented by source logs, development chronology, device and account records,
customer-discovery records, and contributor certifications. It does not capture
conception, off-platform work, source licensing, devices, customer discussions or
pre-employment activity.

Engineering obligations that follow:

- Never rewrite published history; no force-push over `main`, no rebasing
  published commits, no squashing that destroys authorship or dates.
- Never backdate a commit, document or file timestamp.
- Preserve prior versions when language is corrected — change forward as an
  ordinary update.

## Language — customer-facing surfaces

Site copy, PRDs, decks, PR bodies, Drive documents, marketing.

Never write, imply or hint that the idea came from ConstructConnect, that
SpecIndex counters or replaces it, that we know its gaps, pricing, roadmap or
priorities, or that we exploit anything learned confidentially. **Approved
framing is §7 of the brief; use it as written.**

Product positioning, patent freedom-to-operate and third-party acceptable-use
rules are **not** restrictive-covenant controls and live separately in
`docs/PRODUCT_IP_POLICY.md`.

## Roadmap intake gate — before a feature reaches engineering

Mandatory, answered at proposal time, not per commit:

1. Who conceived it?
2. When?
3. What supporting record exists?
4. Did it relate to work performed during employment?
5. Did it use former-employer time, equipment, information or personnel?

## Development request screening — DRAFT, pending counsel

§8 of the brief instructs *"before implementing a material request, answer each
screening question"*; the questions were not supplied. These candidates derive
from the brief's language, each citing its clause. **Counsel's wording replaces
this section entirely.**

**A. Provenance of inputs** *(§2, §4)*

- **A1.** State the source of the data, logic and requirements. Public URL and
  access date for third-party or public-record inputs; or explicitly *"direct
  customer discovery"* (screened per above) or *"original design"*. Recorded, not
  yes/no.
- **A2.** Did any part originate from a former-employer system, account, export,
  email, device or private communication?
- **A3.** Does it require reconstructing a dataset, report, metric or conclusion
  from memory rather than a lawful source?
- **A4.** Does it derive from a remembered internal roadmap, customer complaint,
  pricing detail, performance metric, product gap or strategic priority?
- **A5.** Are transformation logic, extraction prompts and validation methods
  documented?
- **A6.** Can every contributor certify no third-party confidential information
  was contributed?

A2–A4 remain separate questions; a single combined attestation is skimmed.

**B. Who it serves** *(§3, §6)*

- **B1.** Who is the user? Recorded, not yes/no.
- **B2.** Does it closely resemble a ConstructConnect offering?
- **B3.** Does shipping it involve outreach to, or targeting of, anyone on the
  restricted-party register? For generic capability (export, email send), this
  concerns intended use and belongs with whoever operates it.

**C. What it says** *(§7)* — **C1.** Does any copy name ConstructConnect,
compare capabilities, or imply knowledge of its gaps, pricing, plans or
priorities?

**D. Patents** *(§3)* — **D1.** Is any part intended for a patent filing, or an
ownership representation covering a concept possibly conceived during employment?

### Outcomes — three, not two

| Finding | Action |
|---|---|
| Prohibited source, confidential information, restricted solicitation, or evidence manipulation | **Stop and escalate** |
| Competitive similarity, uncertain user category, patent/IP issue, or pre-separation conception | **Pause pending legal clearance** |
| Complete provenance, unrestricted relationships, independently developed requirements | **Proceed subject to ordinary review** |

Uncertainty: preserve, pause, escalate (brief §12).

### Two questions deliberately outside this gate

**Conception date** — belongs at the roadmap intake gate above, answered by the
founder, not inferred by an engineer. **Commercial launch** — §3 permits building
billing systems; merging code must never itself enable paid sales. That control
belongs in release management, outside the merge.

## Escalation

Halt and escalate if a source proves to be ConstructConnect, Dodge, Blue Book or
BuildingConnected content however reached; a contact may be a restricted party;
a feature resembles something known from inside; anyone proposes deleting,
editing or backdating potentially relevant material; or a document cannot be
traced to a lawful source.

---

## Version history

- **Revision 2** — screening questions clarified; pending counsel approval.
- **Revision 1** — initial operational mapping.
