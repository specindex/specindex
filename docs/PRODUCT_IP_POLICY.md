# Product and IP policy

**Revision 1. Product design, freedom-to-operate and third-party terms rules.**

> **These are NOT restrictive-covenant controls.** They were separated from
> `docs/BUILD_COMPLIANCE_BRIEF.md` on legal review, because mixing them with
> employment-compliance rules made the legal status of each unclear. Employment
> obligations live in `docs/COMPLIANCE_BRIEF.md`, which is authoritative.
>
> The patent observations below are engineering-level design constraints adopted
> to reduce risk. They are **not** a freedom-to-operate opinion and no such
> opinion has been obtained.

---

## 1. Third-party terms of use

- **Do not scrape ConstructConnect, Dodge, Blue Book or BuildingConnected.**
  Their acceptable-use terms prohibit it. This constraint stands on the terms
  themselves, independent of any employment question.
- **No paid plan-room content and no plan-room resale.** Government portals and
  the open web are not plan rooms.
- Honour robots.txt and each site's terms of use.
- Where a source's terms are unclear, log it and do not retrieve.

## 2. Design constraints adopted to reduce patent risk

Adopted as engineering constraints. Not a legal opinion.

- **No cross-filtering chart dashboard.**
- **No permit job-cost histogram.** (iSqFt, US 9,633,012 — noted as not
  requiring interactivity.)
- **One-directional citation only.** (Buildsite, US 12,242,990.)

Lead with alerts, digests and API rather than interactive analytics.

## 3. Claims and product positioning

Editorial and evidentiary standards. They also overlap with §7 of the compliance
brief; where they do, **the brief governs**.

- **Never state a claim wider than the evidence.** *"No manufacturer named in the
  N documents we hold"* — never *"none named"*. Absence in our corpus is not
  absence in the world.
- **Do not claim brand-versus-competitor visibility.** 166 of 591,618 projects
  carry any brand mention, and those are tenants rather than manufacturers.
- **Do not lead with project volume.** Sell spec position and citations.
- A specification naming a product is not an award. A spec can name a product and
  the job be built with another.
- Derived scope is never a manufacturer claim. Physical necessity and declared
  trades may be inferred; brand, material or grade may not.

## 4. Data quality standards

- Verify a value's **plausibility**, not merely its presence. Sanity-bound
  numbers before ranking on them.
- Never estimate square footage from value, or value from area.
- A permit fee is not a project cost.
- State absence with its reason rather than rendering an empty cell.
