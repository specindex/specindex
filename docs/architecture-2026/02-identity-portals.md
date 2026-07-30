# SpecIndex Architecture — Identity, Onboarding, Authorization, Portals

*Draft 2026-07-30.*

**Gemini/Vertex review status: Reviewed 2026-07-30.** Real findings below, incorporated into Section 3.

**Build status 2026-07-30: shipped through P4 — see `00-MASTER-ROADMAP.md` for the authoritative per-item breakdown.** In brief: `require_role`, `is_active` enforcement, `/ops/crm`, read-only "view as customer," `org_id`-based Team invite/roster (`org_members` table + `/v1/org/*` endpoints + `components/TeamRoster.tsx`), and `revokeRefreshTokens` wired into a real admin deactivate/reactivate action (`firebase-admin` added to `api/requirements.txt`) are all live. True `createCustomToken` impersonation stays unbuilt — the read-only view it's conditional on hasn't been reported as insufficient by anyone yet.

## Gemini Review Findings (incorporated 2026-07-30)

1. **1-hour JWT revocation gap.** Postgres-side role checks don't help if the endpoint only calls `require_firebase_user` — a deactivated/suspended user's Firebase ID token stays cryptographically valid for up to ~60 minutes regardless of Postgres state. **Fix applied:** add `user_profiles.is_active BOOLEAN DEFAULT true`, and have `require_firebase_user` itself check it (not just `require_role`), so deactivation takes effect on the very next request rather than waiting for role-gated endpoints specifically.
2. **`/v1/me/*` IDOR assessment confirmed secure** — Gemini independently verified `firebase_uid` is derived only from the verified token everywhere, never a parameter. The planned `/v1/admin/customers/{firebase_uid}` isolation as a separate route tree is "correct" per the review — no changes needed there.
3. **Read-only "view as customer" design confirmed sound** — explicitly praised as "an excellent security control" versus live impersonation tokens. No changes.
4. **Split internal staff roles from customer subscription tier into two structures, not one `user_roles` table with 7 mixed values.** Gemini's recommendation: a `user_staff_roles` table (support_admin/super_admin/pipeline_ops only) plus a `subscription_tier` column directly on `user_profiles` (free/trial/pro/team) — these are conceptually different lifecycles (staff grants are rare/manual, tier changes are frequent/automated via Stripe webhooks) and mixing them in one join table makes the common tier-check query do unnecessary work. **Adopted** — revises the `026_user_roles.sql` migration in this doc's Section 3.3 to two structures instead of one.
5. **Per-request Postgres role lookup needs an index and pooling awareness called out explicitly.** Not a design flaw, but flagged as a real operational requirement: index `(firebase_uid)` on both new tables (already planned) and confirm Cloud Run's connection pooling handles the added per-request query volume — revisit a short-TTL cache only if latency data later shows it's needed, not preemptively.

## 0. Ground truth as of today (correcting the brief)

The task brief assumed Clerk is the current auth provider. It is not, as of
yesterday: `db/migrations/025_clerk_to_firebase_auth.sql` renamed
`clerk_user_id` -> `firebase_uid` across `user_profiles`,
`user_tracked_projects`, `user_saved_views`, and `api/main.py` now verifies
Firebase ID tokens (`google_id_token.verify_firebase_token`, project-scoped
audience, Google's public certs, no service-account credential needed),
exposed as `require_firebase_user`, `require_firebase_user_with_email`,
`require_firebase_user_or_build_token`. `components/FirebaseAuthProvider.tsx`
is the client-side replacement for the old `ClerkProviders.tsx` — same
"client SDK only, no server, static Next export" shape, using
`firebase/auth`'s `signInWithPopup` + Google provider. Reasoning documented
inline: one fewer vendor since GCP project `specindex-ai` already backs
Postgres/Cloud Run/Vertex, and Firebase Hosting is already the deploy target.

Also already real and NOT a gap: a minimal admin gate exists today.
`require_admin_user` (api/main.py) checks a valid Firebase session AND the
caller's email against a comma-separated `ADMIN_EMAILS` env var, returns 403
(not 401) for a non-admin authenticated caller. It currently gates exactly
one endpoint, `GET /v1/ops/crm` (the CRM contact list from
`docs/PRD_SIGNUP_CRM.md`). This is the seed of the authorization model below,
not a parallel system to replace.

Everything below is written against Firebase Auth as the real current
provider. Where the brief's Clerk-specific questions still have a real
Firebase equivalent (SSO/enterprise, org/seat model), they're answered as
Firebase equivalents.

---

## 1. Onboarding

### 1.1 What exists today
- Sign-in: Google OAuth via `signInWithPopup`, Firebase Auth client SDK.
  No email/password path configured yet (single provider).
- First-sign-in capture: `components/onboarding/AuthSync.tsx` fires once per
  sign-in, calls `GET /v1/me/profile`; if `onboarded` is false it renders
  `ProfileCaptureModal` (territory states, one product category, optional
  company), pre-filled from any anonymous `localStorage` state. Submission
  hits `POST /v1/me/profile`, which upserts `user_profiles` keyed on
  `firebase_uid`.
- Per `docs/PRD_SIGNUP_CRM.md` (already-decided, not yet built): extend
  `user_profiles` with `full_name`, `phone`, `role_title`, `lead_source`,
  `lifecycle_stage`, `notes`; capture `full_name`/`lead_source` in the same
  `POST /v1/me/profile` call rather than a separate sync (Gemini flagged the
  separate-sync design as fragile in that earlier review — same lesson
  applies here: don't add a second write path where one call already works).
- A second, disconnected capture point exists: `DemoSection.tsx` →
  `POST /v1/contact` → `contact_submissions` (name, email, company,
  categories, source_path). PRD's `crm_contacts` view already reconciles
  these two by lower-cased/trimmed email, deduplicated to latest row.
- Sign-out cleanup already handles the shared-machine case: `AuthSync`
  clears `localStorage` territory/category on a true→false sign-in
  transition so a second person on the same browser doesn't inherit them.

### 1.2 What's missing
- **Company/team concept.** `user_profiles` has a free-text `company`
  column, not a `companies` entity. There is no way today to say "these
  three signed-in users are the same buying org" — which matters the moment
  Team-tier seat management (Section 4) exists. No action needed at Free/Pro
  volumes; flagged as a real blocker once Team tier ships.
- **No welcome/activation flow beyond the capture modal.** No "what to do
  next" nudge (e.g., "here are 3 tracked projects in your territory"),
  and no verified-email requirement (Google sign-in implies a verified
  email already, so low urgency, but worth confirming if an email/password
  provider is ever added).
- **No org/domain-based auto-join.** A user from `acme.com` who signs up
  has no path to "you're joining Acme's existing SpecIndex account" — this
  is the same gap as company/team, restated at the invite level.
- **PRD's schema extension isn't applied yet.** `full_name`, `phone`,
  `lifecycle_stage`, etc. don't exist as columns yet (only in the PRD text)
  — this is Phase 1 of an already-agreed plan, just not executed.

### 1.3 Decision
Build on the PRD as written — do not redesign onboarding, execute it. The
one addition this doc proposes on top of the PRD: add a nullable
`org_id BIGINT` to `user_profiles` now (unused, unenforced) as a forward
seam for Team-tier seats, the same "reserve the column now, wire it up
later" move `clerk_org_id` used to be before the Firebase rename made it
`firebase_org_id`-shaped and effectively dead. Cheap to add today, expensive
to backfill later.

---

## 2. Authentication

Current state (Firebase ID token verification via Google's public certs,
bearer-token-only, no cookies, `require_firebase_user*` dependency family) is
sound for where the product is. Not re-litigating it. Real gaps:

- **No enterprise/SSO path.** No SAML/OIDC federation for a buying org that
  mandates Okta/Azure AD sign-in. Firebase Auth supports SAML/OIDC providers
  on the **Google Cloud Identity Platform** upgrade (paid tier, per-MAU
  pricing) — this repo has no cost estimate or decision on file for that
  upgrade; treat it as a real open item, not a solved one, and get a
  current quote before promising it to any enterprise prospect. Until then,
  "does your team support SSO" has an honest answer: no, not yet, roadmapped
  behind Team-tier demand.
- **No session/token lifecycle policy documented.** Firebase ID tokens
  self-expire (~1 hour) and the client SDK silently refreshes them; that's
  Firebase default behavior, not something this repo configures. No documented
  policy on: forced sign-out (e.g. offboarding a seat), refresh token
  revocation on suspicious activity, or max session age. Firebase Admin SDK
  supports `revokeRefreshTokens(uid)` server-side — not called anywhere
  today. This becomes a real requirement the moment Section 3's admin role
  can deactivate a user.
- **No service-to-service auth.** Every current backend dependency
  (`require_firebase_user`, `require_admin_user`, `require_firebase_user_or_build_token`)
  authenticates a human or the one shared `SPECINDEX_BUILD_TOKEN` static
  secret. There's no pattern yet for one internal service calling another
  (e.g., a future internal tool calling `api/main.py`) — when that need
  arises, don't reuse `SPECINDEX_BUILD_TOKEN`'s shape (single static shared
  string, no expiry, no scoping); use short-lived GCP service-account
  identity tokens instead, since Cloud Run already supports verifying those
  natively.
- **MCP server auth — connection point only.** A separate MCP data-access
  plan is being designed elsewhere in this project; this doc only notes the
  seam: MCP tool calls will need to authenticate as *some* SpecIndex
  identity to hit `/v1/me/*`-shaped or admin-shaped endpoints. Whatever that
  design lands on (a scoped API key, a Firebase custom token, an
  OAuth client-credentials flow) should reuse the role model in Section 3
  rather than invent a parallel permission system — flagging this as a
  cross-doc dependency, not designing it here.

---

## 3. Authorization (the real gap)

### 3.1 Current state
None. Every `require_firebase_user`-gated endpoint treats every signed-in
user identically. The only exception is the one-off `require_admin_user`
allowlist check gating `GET /v1/ops/crm`. There is no `role` concept,
no tiering enforcement (Free/Pro/Team from `docs/product-strategy.md`'s
Monetization section are pricing-page copy today, not enforced anywhere in
`api/main.py`), and no ops/pipeline role at all.

### 3.2 Roles needed, concretely
1. **End-customer tiers** — `free`, `trial`, `pro`, `team` (matches
   `docs/product-strategy.md`: Free = limited GA browse + 1 brand check/wk;
   Pro = unlimited GA search + brand alerts + competitor compare; Team =
   multi-brand books + territory seats + export/CRM sync).
2. **Internal admin** — support/sales-ops staff who need to view (not
   necessarily edit) customer data: profiles, tracked projects, CRM
   contacts. Distinct from...
3. **Internal super-admin** — Asif/founder-level, today's `ADMIN_EMAILS`
   allowlist, full read on everything including `/ops/crm`'s PII.
4. **Data-pipeline/ops role** — the people (today: nobody but Asif, but
   this is written for the 100-engineer future) running ingestion, who need
   `/coverage`, `/ops`, `/map` visibility but have no reason to see customer
   PII (`user_profiles`, `contact_submissions`) at all.

### 3.3 Recommendation: Postgres is the source of truth for roles, not Clerk/Firebase metadata

Firebase custom claims (the equivalent of what Clerk Organizations/metadata
would have done) *can* hold a role, set via the Admin SDK
(`setCustomUserClaims`), and would auto-propagate into every ID token,
which is attractive — no extra DB round-trip to check a role. But three
things point at Postgres instead, as the sole source of truth:

- **Propagation lag.** Custom claims only take effect on the *next* token
  refresh (client SDK refreshes roughly hourly, or on explicit
  `getIdToken(true)`), not the moment the role changes. Revoking an admin's
  access needs to be immediate (compliance/support-escalation reality at
  100 engineers), and Postgres can enforce that on every request; a stale
  claim in an already-issued token cannot.
- **Multi-role and pricing-tier logic already lives in Postgres.**
  `user_profiles` already tracks lifecycle/company/territory server-side.
  Splitting "what tier are they" (Postgres, needed for billing logic
  anyway) from "what role do they have" (Firebase claims) means two systems
  to keep in sync for what's conceptually one authorization question.
- **Firebase custom claims have a hard 1000-byte total limit** across all
  claims on a token — fine for a single role string, cramped the moment
  multi-role or scoped-permission lists are needed (e.g. a Team-tier user
  who is also, separately, an internal QA tester).

**Recommendation: a `user_roles` join table in Postgres, checked per-request
by the FastAPI dependency layer, NOT Firebase custom claims.** Firebase
stays purely an identity provider (who is this person, is their token
valid) — it should not also become the authorization store. This is a
real tradeoff, not a free lunch: it costs one extra indexed lookup per
authorized request (cheap — see below) in exchange for immediate
revocation and a single place multi-role logic lives.

```sql
-- Migration: 026_user_roles.sql
-- Revised per Gemini review: staff roles (rare, manually granted) and
-- customer subscription tier (frequent, Stripe-webhook-driven) are
-- different lifecycles -- kept as two structures, not one mixed table.
CREATE TABLE IF NOT EXISTS user_staff_roles (
  id            BIGSERIAL PRIMARY KEY,
  firebase_uid  TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('support_admin', 'super_admin', 'pipeline_ops')),
  granted_by    TEXT NOT NULL,   -- firebase_uid of whoever granted it
  granted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (firebase_uid, role)
);

CREATE INDEX IF NOT EXISTS user_staff_roles_firebase_uid ON user_staff_roles (firebase_uid);

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS subscription_tier TEXT NOT NULL DEFAULT 'free'
    CHECK (subscription_tier IN ('free', 'trial', 'pro', 'team')),
  ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;
-- is_active: checked directly inside require_firebase_user (not just
-- require_role) so a deactivated user's still-valid Firebase ID token
-- (self-expires ~1hr) stops working on the very next request, not up to
-- an hour later -- closes the JWT-revocation gap Gemini flagged.
```

A join table, not a single `role` column on `user_profiles`, because a user
is genuinely multi-role in the target state: a `team`-tier paying customer
who is *also* granted `support_admin` for a specific pilot account is a real
future case, and `user_profiles` shouldn't need a schema change to express
it. Pricing tier and internal-staff role are the same kind of fact
(a grant), so one table, not two.

A single-row `role` on `user_profiles` was the cheaper alternative
considered and rejected: it's simpler for the 99% single-role case, but it
means "grant someone a second role temporarily" requires either a
comma-hack column or a migration later — the join table costs one extra
`CREATE TABLE` now to avoid that migration later.

### 3.4 Enforcement pattern

```python
def require_role(*allowed: str):
    """Factory: returns a FastAPI dependency requiring one of the given
    Postgres-stored roles, on top of a valid Firebase session. Verifies the
    token itself (doesn't trust an upstream dependency ran first) — same
    non-bypassable-by-hitting-the-endpoint-directly guarantee
    require_admin_user already documents."""
    def _dep(request: Request) -> tuple[str, str]:
        firebase_uid = require_firebase_user(request)
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT role FROM user_roles WHERE firebase_uid = %s "
                "AND (expires_at IS NULL OR expires_at > now())",
                (firebase_uid,),
            )
            roles = {r[0] for r in cur.fetchall()}
        if not roles & set(allowed):
            raise HTTPException(status_code=403, detail="Not authorized")
        return firebase_uid, roles
    return _dep

# Usage:
@app.get("/v1/ops/crm")
def list_crm_contacts(_: tuple = Depends(require_role("support_admin", "super_admin"))):
    ...

@app.get("/v1/admin/customers/{firebase_uid}")
def view_customer_as_admin(firebase_uid: str, _: tuple = Depends(require_role("support_admin", "super_admin"))):
    ...
```

`require_admin_user`'s `ADMIN_EMAILS` allowlist becomes the seed data for
`super_admin` rows (a one-time backfill insert), not a parallel mechanism
kept alongside the new table — two authorization systems checking the same
endpoint is the exact bug class to avoid here.

### 3.5 IDOR / impersonation risk on the existing `/v1/me/*` pattern

Reviewed every existing `/v1/me/*` handler
(profile, tracked-projects, saved-views, ask): each one derives
`firebase_uid` from the verified token itself
(`firebase_uid: str = Depends(require_firebase_user)`), never from a path
or body parameter — so there is no IDOR today (a user cannot pass someone
else's ID and read their data, because no endpoint accepts one). This
pattern must be preserved for the new admin view: `GET
/v1/admin/customers/{firebase_uid}` (Section 4) is the first endpoint in
this codebase where a caller *does* supply someone else's identifier, and
it must be a genuinely different, explicitly role-gated route — never a
query parameter bolted onto the existing `/v1/me/*` handlers. Mixing "my
own data, identity from token" and "someone else's data, identity from
request" in the same handler is the single highest-risk design mistake
available here; keep them as physically separate endpoints with separate
dependencies.

---

## 4. User portal vs. Admin portal

### 4.1 User portal (`SignedInHome` → grows into this)
Exists today as `components/marketing/SignedInHome.tsx`: a Feed + Tracked
pipeline view, no dedicated "Account" page (`SiteHeader.tsx` explicitly
notes Firebase ships no prebuilt account-management UI, unlike Clerk).
Needs to grow into:
- **Account/profile settings page** — currently only exists as the
  first-sign-in modal; no page to revisit/edit territory, categories,
  company, name, phone after the fact.
- **Billing** — no billing integration exists at all yet (no Stripe
  customer ID anywhere in `user_profiles` or elsewhere in this repo).
  Needed before Pro/Team tiers can actually be sold, not before this doc's
  P0/P1 window.
- **Team/seat management** — blocked on the `org_id` seam from Section 1.3;
  a Team-tier admin needs to invite/remove seats and see a roster, which
  needs the org concept before it needs a UI.
- **Usage/quota visibility** — Free tier's "one brand check/week" limit
  (per `docs/product-strategy.md`) isn't enforced or displayed anywhere
  today; needs a usage-counter table and a rate-limit dependency before
  it's a real Free-tier gate rather than pricing-page copy.

### 4.2 Admin portal (fully unbuilt)
Real requirements, in priority order:
1. **Customer account visibility** — who signed up, what tier/role
   (Section 3's `user_roles`), last activity. New read-only page,
   `support_admin`+ gated.
2. **"View as customer" — read-only view, not session impersonation.**
   Recommendation: never mint a real session as the customer (classic
   impersonation risk: an admin session that can *write* as the customer,
   or that leaves an audit gap about who actually performed an action).
   Instead, build a parallel read-only admin query path — the same
   `require_role("support_admin", ...)`-gated endpoint pattern from 3.4,
   returning the customer's profile/tracked-projects/saved-views data
   under the *admin's* identity and role, logged as an admin action, never
   an actual auth token for the customer's account. If true "log in as
   this user" (with write access) is ever needed for a support case,
   Firebase Admin SDK's `createCustomToken(uid)` can mint one, but it must
   be short-lived, single-use, and every action taken under it logged
   distinctly from the customer's own actions — treat this as a P3/P4
   feature to build only if the read-only view proves insufficient, not a
   default.
3. **Coverage/pipeline health consolidation.** `/coverage`, `/ops`,
   `/map` already exist as separate unauthenticated-but-`noindex` pages
   (deliberately not admin-gated today — per the PRD's own reasoning, they
   expose only operational metadata nobody could misuse). Recommendation:
   don't force these behind the new role system just for consistency —
   the PRD already drew this line correctly for `/ops/crm` vs. the rest.
   Do add them as *linked* pages inside the new admin portal shell (so
   there's one navigation surface), without changing their auth
   requirement. Only `/ops/crm` (and the new customer-visibility view)
   carry real PII and need `support_admin`+.
4. **Content/config management** — nothing in the current repo suggests a
   CMS-shaped need yet (no manually-curated marketing content beyond
   static pages). Not a real requirement today; revisit only if a
   non-engineer needs to edit site copy without a code deploy.

---

## 5. Phased build plan

| Phase | Scope |
|---|---|
| 1 | `026_user_roles.sql` migration; backfill `ADMIN_EMAILS` into `super_admin` rows; `require_role()` dependency factory; re-point `/v1/ops/crm` at it |
| 2 | Execute `docs/PRD_SIGNUP_CRM.md` Phase 1–3 as already planned (schema extension, modal fields, `/ops/crm` UI) — unblocked independently of roles work |
| 3 | Add `free`/`trial`/`pro`/`team` role rows at signup/Stripe-webhook time; enforce Free-tier usage caps server-side |
| 4 | Admin portal shell: customer list + read-only "view as customer" query path, consolidating links to `/coverage`/`/ops`/`/map` |
| 5 | User portal growth: account settings page, billing (Stripe customer id on `user_profiles`), usage/quota widget |
| 6 | Org/seat model: `org_id` wiring, Team-tier invite/roster flow |
| 7 (conditional) | Enterprise SSO via Identity Platform upgrade, if/when a Team-tier prospect requires it — get a real cost quote first |

---

## 6. Priority action items

- ✅ SHIPPED 2026-07-30 as migration 027 (026 taken by concurrent work): Add `user_staff_roles` (staff-only join table) + `subscription_tier`/`is_active` columns on `user_profiles`.
- ✅ SHIPPED 2026-07-30: Build `require_role()` FastAPI dependency factory and re-point `/v1/ops/crm` at it instead of `require_admin_user`
- ✅ SHIPPED 2026-07-30 (live): Backfill current `ADMIN_EMAILS` allowlist into `user_staff_roles` as `super_admin` rows
- ✅ SHIPPED 2026-07-30: Check `is_active` inside `require_firebase_user` itself, not just `require_role` — closes the ~1hr JWT-revocation gap Gemini flagged
- P1: Execute `docs/PRD_SIGNUP_CRM.md` Phase 1 migration (full_name, phone, lifecycle_stage, etc. on user_profiles)
- P1: Build admin portal customer-list page gated on `support_admin`/`super_admin`
- P1: Build read-only "view as customer" admin query path (never mint a real customer session)
- P1: Keep `/coverage`, `/ops`, `/map` on their current unauthenticated-but-noindex pattern; only link them into the admin shell nav
- P2: Enforce Free-tier "1 brand check/week" quota server-side with a usage-counter table
- P2: Add nullable `org_id` column to `user_profiles` as a forward seam for Team-tier seats
- P2: Add account/settings page to the user portal for post-onboarding profile edits
- P3: Add Stripe customer id to `user_profiles`; build billing page
- P3: Design short-lived `createCustomToken`-based true impersonation only if the read-only admin view proves insufficient
- P4: Team-tier org/seat invite-and-roster flow using the `org_id` seam
- P4: Call `revokeRefreshTokens(uid)` from an admin "deactivate user" action
- P5: Get a real Identity Platform SSO cost quote before promising enterprise SSO to any prospect
- P5: Replace `SPECINDEX_BUILD_TOKEN` static shared secret with short-lived GCP service-account identity tokens once any second internal service needs to call `api/main.py`
