# Legal backlog — Compliance Framework Review

**Received 2026-08-07. NOT ACTIONED. Stored for scheduling, not yet worked.**

> Counsel's review of the revised compliance documents, reproduced as received.
> **Status per counsel: DRAFT — NOT APPROVED FOR OPERATIONAL RELIANCE.**
>
> Nothing in this file has been implemented. One item (P0 #3) has an immediate
> operational consequence and is flagged at the end; the rest await scheduling.

---

## SpecIndex Compliance Framework Review
### Working Draft for Revision | August 7, 2026
**DRAFT — NOT APPROVED FOR OPERATIONAL RELIANCE**

### Overall Assessment

The revised documents are materially improved, but the control framework should not yet be approved for operational reliance. The build brief is substantially corrected. The principal remaining risks are:

- Conflict with the unchanged authoritative master brief.
- Material provenance gaps.
- A malformed source inventory with possible downstream contamination.
- Overconfidence in unverified terms-of-use and patent assumptions.
- Missing privacy, copyright, retention, and takedown controls.

### Priority 0 — Must Fix Before Reliance

**1. Revise the Authoritative Compliance Brief**

The updated build brief correctly states that no development activity is categorically permitted. However, it defers to the authoritative master brief, which still describes manufacturer-focused development and general infrastructure as permitted. That creates an irreconcilable hierarchy problem. The employment agreement may restrict private or unpaid development if it constitutes similar services for a competing business.

Recommended replacement language:

> Potentially lower-risk development direction, subject to legal clearance. No activity is categorically permitted merely because it is private, unpaid, infrastructure-focused, public-data-based, or manufacturer-facing.

Until the master brief is revised, the updated build brief cannot cure the master document.

**2. Correct the Project-Source Mapping**

The build brief states that a source URL exists on project and document rows. The disclosed project schema instead shows a `sources` object, not a dedicated project-level source URL. Determine and document:

- The structure of the sources object.
- Whether each factual field can be traced to a specific source.
- Whether multiple sources are preserved separately.
- Whether source changes are versioned.
- Whether derived conclusions retain field-level lineage.

A project-level list of URLs is insufficient if individual claims cannot be traced to supporting records.

**3. Freeze the Malformed Source Inventory**

The provenance document reports that 29 of 47 rows in one source inventory have shifted fields affecting URLs and notes. That is a material chain-of-custody defect.

- Preserve the defective version.
- Stop new ingestion from that inventory.
- Correct it prospectively without overwriting history.
- Identify every run and downstream record that used affected rows.
- Revalidate source URLs, access basis, and resulting records.
- Record the remediation in an incident log.

**4. Address the Missing Provenance Controls**

The schema confirms that source ownership, license or terms, access authorization, authentication status, classification, retention restrictions, and contributor certification are absent. Adopt a controlled remediation framework:

- Block onboarding of new sources without source-level approval.
- Create a versioned source registry.
- Backfill existing sources by risk tier.
- Quarantine sources whose lawful access basis cannot be established.
- Require contributor certification before accepting new external material.

### Priority 1 — Important Corrections

**5. Tighten the Proceed Outcome**

Replace "Proceed subject to ordinary review" with:

> Proceed to the next internal review stage only. This screening result does not constitute legal clearance, a waiver, or a determination that the activity falls outside the restrictive covenant.

**6. Remove the Remaining Billing-System Implication**

Replace any implication that building billing functionality is permitted with:

> Billing functionality must remain disabled unless separately cleared. Building or merging functionality does not itself establish compliance.

**7. Add a Source-Terms Evidence Package**

For every source, preserve:

- Terms and license version applicable on the access date.
- Archived copy or hash.
- Source owner and access method.
- Authentication status and applicable API documentation.
- Rate, reuse, attribution, and retention restrictions.
- Approval status.

Public accessibility is not equivalent to unrestricted copying, extraction, storage, or resale.

**8. Protect Quarantine Materials Properly**

- Identify a named custodian and access-control list.
- Record the date and reason for quarantine.
- Preserve original metadata and a chain-of-custody log.
- Prohibit embedding, extraction, indexing, or automated processing.
- Permit release or deletion only upon authorized review.

### Product and IP Policy

**9. Qualify Terms-of-Use Conclusions**

Categorical legal conclusions should not be used unless current terms were reviewed and archived. Recommended language:

> Company policy prohibits automated retrieval from these services pending documented review of current terms, licenses, access controls, and applicable law.

**10. Reframe the Patent Section**

Rename the section "Interim Product Restrictions Pending Patent Review" and add:

> Compliance with these restrictions does not establish freedom to operate. No feature should be treated as cleared based solely on avoiding the identified implementations.

The cited patents should be claim-charted by patent counsel before the policy attributes meaningful risk reduction to the restrictions.

**11. Date Dynamic Factual Metrics**

- Add an as-of date.
- Identify the dataset version and query or report identifier.
- Assign an owner responsible for refreshing or retiring the statement.

### Missing Policy Layer

Create a separate **Data Rights, Privacy, and Retention Policy** addressing:

- Personal information in permits and public records.
- Copyright and database rights.
- Government-record reuse conditions.
- Data minimization and retention schedules.
- Correction and takedown requests.
- Access controls and security incidents.
- Embeddings and derived data.
- Vendor processing.
- Restrictions on public display or resale.

Public records can remain subject to privacy, copyright, contractual, and use restrictions.

### Source References

- `BUILD_COMPLIANCE_BRIEF.md` — revised development-direction and screening language.
- `COMPLIANCE_BRIEF.md` — Section 3, permitted-development language requiring revision.
- Employment Agreement - Asif Hussain (1).pdf — Section 3(g)–(h).
- `DATA_PROVENANCE_SCHEMA.md` — mandatory-field status, live schema, and known gaps.
- `PRODUCT_IP_POLICY.md` — third-party terms and interim patent-risk provisions.

---

## Engineering notes — not legal comment

**P0 #3 has an immediate operational consequence.** It instructs: *"Stop new
ingestion from that inventory."* The inventory is
`coverage/data/project-discovery-sources.csv` (29 of 47 rows column-shifted).

Which adapters read it:

| adapter | reads that CSV | status |
|---|---|---|
| A1 Socrata | endpoints hand-verified, config in `config/socrata/*.yaml` | already built |
| A2 ArcGIS | endpoints hand-verified, config in `config/arcgis/*.yaml` | already built |
| A5 Accela | endpoints hand-verified, config in `config/accela/*.yaml` | already built |
| **A7, A8** | **yes — would read it directly** | **not built** |
| A4 SAM.gov | no — uses the SAM API | running |

A1/A2/A5 configs were built from **live endpoint probes**, not from the CSV
fields, so the shifted columns did not propagate into them. That is worth
verifying rather than asserting before any remediation claim is made.

**Not started, per instruction.** P0 #2 (field-level lineage vs the `sources`
object) and P0 #4 (seven absent provenance fields) both require schema
migrations and should be scheduled deliberately.
