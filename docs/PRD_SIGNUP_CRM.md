# SpecIndex Sign-Up → CRM Plan

*Draft 2026-07-29 — revised after a Gemini (Vertex) review pass: fixed a real PII-exposure risk in the admin view's auth model, fixed a SQL join bug (case sensitivity + duplicate-row fan-out), cut an over-engineered custom-editing phase in favor of a database GUI or export, and simplified the name-capture mechanism. Updated again: swapped the auth provider from Clerk to Firebase Auth throughout, a closer fit since the site already deploys on Firebase Hosting.*

## 0. What already exists (don't rebuild this)

Before proposing anything new, here's the current state, confirmed directly against the live repo:

- **Auth is already live via Firebase Auth** (`components/FirebaseAuthProvider.tsx`), using `firebase/auth`'s client SDK, a natural fit since the site already deploys to Firebase Hosting and needs no additional server runtime for token verification on the client side.
- **`/projects/` is already gated behind sign-in** (`components/ProjectsGate.tsx`) — an anonymous visitor never even fetches project data client-side.
- **A first-sign-in capture modal already exists** (`components/onboarding/ProfileCaptureModal.tsx`): asks for territory (states), product category, and company (optional), and writes to a `user_profiles` Postgres table via `POST /v1/me/profile` (`api/main.py:1203`).
- **A second, separate capture point already exists**: the homepage demo-request form (`components/marketing/DemoSection.tsx`) writes to a `contact_submissions` table via `POST /v1/contact`, capturing first name, last name, email, company, categories, and `source_path` (which page the request came from).

So SpecIndex already captures basic signup information into a database today. What it does **not** have is anything that functions like a CRM: the two capture points are disconnected, neither has a lifecycle/pipeline stage, there's no name or phone on the signed-in-user side, and there is no internal view where a person can actually look at a list of leads and work them. That gap is what this plan addresses.

## 1. The core problem with today's setup

1. **Two capture points, no shared identity.** A visitor who fills out the demo form and *also* signs in and completes onboarding shows up as two unrelated rows (`contact_submissions` and `user_profiles`), joinable only by matching email manually.
2. **No lifecycle stage anywhere.** Nothing distinguishes "just signed up," "onboarded and browsing," "requested a demo," "in a sales conversation," "trialing Pro," "paying," or "churned." A CRM is fundamentally a system for tracking where each contact sits in that progression — today there's no field for it at all.
3. **Missing basic contact fields on the signup side.** `user_profiles` has no name and no phone. Firebase Auth itself holds a name/email internally, but it isn't synced into a queryable column.
4. **No internal view to work the data.** Both tables are queryable only via `psql` or the read API. There's no page — not even an internal `/ops`-style one — where the data is browsable, searchable, or editable as a worklist.

## 2. Proposed schema changes

**Recommendation: don't create a third, separate "CRM" table yet.** With two existing tables and pre-revenue traffic volume, a third table to reconcile against is more complexity than the data justifies right now. Instead:

### 2.1 Extend `user_profiles` (new migration, additive only)

```sql
ALTER TABLE user_profiles
  ADD COLUMN full_name       TEXT,
  ADD COLUMN phone           TEXT,
  ADD COLUMN role_title      TEXT,
  ADD COLUMN lead_source     TEXT,
  ADD COLUMN lifecycle_stage TEXT NOT NULL DEFAULT 'signed_up',
  ADD COLUMN notes           TEXT;

-- lifecycle_stage values (soft-enforced in the API layer, not a DB enum,
-- so adding a stage later doesn't require a migration):
-- 'signed_up' -> 'onboarded' -> 'demo_requested' -> 'in_conversation'
-- -> 'trialing' -> 'paying' -> 'churned'
```

`full_name` and a coarse `lead_source` (e.g. `"organic"`, `"demo_form"`, `"referral"`) should be captured once, at Firebase Auth sign-up if possible (Firebase Auth collects name during its own sign-up form) and synced via `AuthSync` — avoiding yet another manual field for the user to fill in. `phone` and `role_title` become optional fields on the existing `ProfileCaptureModal`, not mandatory ones (see Section 4 on friction).

### 2.2 Leave `contact_submissions` as-is, but add a linking column

```sql
ALTER TABLE contact_submissions
  ADD COLUMN firebase_uid TEXT;
```

Nullable, populated at write time if the visitor happens to be signed in when they submit the demo form (`onAuthStateChanged` already has this value client-side — it's a one-line change to include it in the POST body). This gives a real join key without merging two tables that serve genuinely different moments (anonymous interest vs. authenticated product usage).

### 2.3 A merged view, not a merged table

The first-draft version of this view had a real bug, caught in review: joining two tables on raw `email` breaks in two ways — case differences (`User@x.com` vs `user@x.com` never match) and fan-out, where a contact who submitted the demo form more than once produces duplicate joined rows. Fixed version, deduplicating `contact_submissions` to its latest row per normalized email before joining:

```sql
CREATE VIEW crm_contacts AS
WITH latest_submission AS (
  SELECT DISTINCT ON (LOWER(TRIM(email)))
    email, first_name, last_name, company, categories, source_path, created_at
  FROM contact_submissions
  ORDER BY LOWER(TRIM(email)), created_at DESC
)
SELECT
  COALESCE(up.firebase_uid, 'anon-' || md5(LOWER(TRIM(cs.email)))) AS contact_key,
  COALESCE(up.full_name, cs.first_name || ' ' || cs.last_name) AS name,
  COALESCE(up.email, cs.email) AS email,
  COALESCE(up.company, cs.company) AS company,
  up.territory_states,
  COALESCE(up.categories, string_to_array(cs.categories, ',')) AS categories,
  up.lifecycle_stage,
  up.lead_source,
  cs.source_path AS demo_request_source,
  cs.created_at AS demo_requested_at,
  up.onboarded_at,
  up.notes
FROM user_profiles up
FULL OUTER JOIN latest_submission cs
  ON LOWER(TRIM(up.email)) = LOWER(TRIM(cs.email));
```

A `VIEW`, not a table — always reflects live data, no dual-write bugs, no backfill migration risk. This is the single query the CRM admin page (Section 3) reads from. `contact_key` uses a stable hash instead of a raw row ID so it doesn't shift if `latest_submission` re-picks a different row after a new demo-form resubmission.

## 3. The internal CRM view

**This does NOT follow the existing `/ops`/`/coverage` pattern, and that's a deliberate deviation, not an oversight.** Those pages are unauthenticated-but-`noindex` because they expose operational metadata (pipeline health, county coverage stats) — nothing a stranger with the URL could misuse. `/ops/crm` is different in kind: it renders real names, emails, and phone numbers. "Hidden URL + `noindex`" is security through obscurity for that kind of data, not real protection, and treating it the same as the existing `/ops` pages would be a genuine PII-exposure bug, not a style inconsistency. This was flagged in review and is now a hard requirement, not a nice-to-have:

- **Real auth required, both sides.** `/ops/crm`'s frontend route must sit behind Firebase Auth sign-in (same `onAuthStateChanged` pattern `ProjectsGate` already uses), and the backend endpoint (`GET /v1/ops/crm`) must independently verify the Firebase ID token server-side and check the caller's email against an admin allowlist (e.g. an `ADMIN_EMAILS` env var) — never trust "the frontend already checked," since the API is a public URL regardless of what the site does. A non-admin authenticated user and a fully anonymous visitor must both get a 401/403, not a filtered view.
- **New route: `/ops/crm`.** Table of `crm_contacts`, sortable/filterable by lifecycle stage, territory, category, and demo-requested-vs-not.
- **Read-only is the actual target, not a placeholder step.** Render the view, admin-gated as above. This alone turns "data trapped in two Postgres tables" into "a list a person can actually work from," which is most of the value.
- **Cut: a custom editable UI.** The first draft of this plan proposed a `PATCH /v1/ops/crm/{contact_key}` endpoint with logic to route updates to different tables depending on whether `contact_key` was a real Firebase Auth user or a synthetic anonymous one. That's real backend complexity (a second write path, edge cases for creating a `user_profiles` row on the fly for a contact who never signed in) to save typing in a database GUI — a classic solo-founder overbuild. Instead: connect a database GUI (e.g. TablePlus, or `psql` directly) straight to Cloud SQL for stage/notes updates until lead volume genuinely requires a shared, non-technical-friendly editing UI.
- **Explicitly out of scope for now:** email sequencing, task/reminder scheduling, pipeline Kanban boards, and the custom editing UI above. If lead volume grows enough to need real collaborative CRM features, that's the point to export the (by-then battle-tested) `crm_contacts` view into a real CRM tool (HubSpot free tier, Airtable, Attio) — not the point to keep building bespoke features in-house indefinitely.

## 4. Sign-up flow changes

- Keep the modal's existing "Skip for now" affordance — mandatory fields at first sign-in measurably hurt onboarding completion, and territory/category are the two fields that actually power the personalized `/projects/` view, so those stay the only required ones.
- Add `phone` and `role_title` as new optional fields in `ProfileCaptureModal`, styled identically to the existing optional `company` field.
- **Populate `full_name` directly in the existing `POST /v1/me/profile` call, not via a separate sync mechanism.** The first draft of this plan suggested relying on `AuthSync` to push Firebase Auth's name into Postgres as a background sync — flagged in review as fragile (ad-blockers, a closed tab, or any client-side failure silently leaves the row without a name). The simpler, more reliable fix: the modal already runs client-side where Firebase Auth's `onAuthStateChanged`/`auth.currentUser` has the name available, so just include `full_name` directly in the same `onSubmit` payload `ProfileCaptureModal` already sends — one write, no separate sync path to fail. `lead_source` follows the same rule: capture it from the referring page at the moment of that same submit call.

## 5. Phasing

| Phase | Scope | Effort |
|---|---|---|
| 1 | Migration: extend `user_profiles`, add `firebase_uid` to `contact_submissions`, create the deduplicated, case-insensitive `crm_contacts` view | Small |
| 2 | `ProfileCaptureModal`: add optional phone/role fields; include `full_name`/`lead_source` directly in the existing submit payload | Small |
| 3 | `/ops/crm` — Firebase-Auth-gated (frontend + backend), admin-allowlist-checked, read-only list view | Medium |
| — cancelled | ~~Custom editable CRM UI~~ — use a database GUI (TablePlus/`psql`) directly against Cloud SQL instead | — |
| 4 (later, conditional) | Export `crm_contacts` to a real CRM tool (HubSpot free tier, Airtable, Attio) once lead volume/team size justifies collaborative editing | Not started |

## 6. Open questions for founder decision

1. Should `lifecycle_stage` transitions ever be automatic (e.g. auto-set to `demo_requested` when a signed-in user submits the contact form) or always manual? Recommendation: automatic for the objective transitions (signed_up, onboarded, demo_requested), manual for the subjective sales ones (in_conversation, trialing, paying, churned).
2. `/ops/crm` now requires real auth from day one (Section 3) regardless of scale — the open question is just who's on the `ADMIN_EMAILS` allowlist initially (founder-only vs. anyone else already working leads) and how that list gets maintained as it grows.
3. At what lead volume does a real CRM tool become worth the integration effort over the in-house view? No need to answer now — just flagging it as the eventual off-ramp so Phase 3/4 don't turn into an ever-expanding bespoke CRM.
