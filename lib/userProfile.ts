// Talks to the /v1/me/profile endpoints added in PR 2 (api/main.py,
// db/migrations/021_user_profiles.sql). Every call fetches a fresh Firebase
// ID token immediately before the request via getIdToken() -- tokens are
// short-lived (~1hr) and Firebase's SDK auto-refreshes the underlying
// session, but re-fetching per call keeps this code from ever holding a
// stale token across a page that's been open a while. The `template`
// option on GetToken is a no-op carried over from the Clerk-era signature
// (a Clerk JWT Template was needed there to add an `email` claim; Firebase
// ID tokens include it natively) -- kept only so call sites didn't need to
// change shape during the auth-provider swap.

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

// Fired on `window` whenever AuthSync writes a server profile into
// localStorage (territory/category keys shared with ProjectsDashboard.tsx).
// localStorage itself only notifies OTHER tabs (the `storage` event never
// fires in the tab that made the write), so a component already mounted on
// /projects/ when sign-in resolves needs this to pick up the new values --
// otherwise it's stuck showing whatever it read at its own initial mount.
export const PROFILE_SYNC_EVENT = "specindex:profile-sync";

export type ProfileSyncDetail = { territory: string[]; category: string };

export type UserProfile = {
  onboarded: boolean;
  company: string | null;
  territory_states: string[];
  categories: string[];
  // Added for the account/settings page (docs/architecture-2026 P2) --
  // GET /v1/me/profile now returns these too, previously write-only.
  full_name: string | null;
  phone: string | null;
  role_title: string | null;
  subscription_tier: string;
};

export type UserProfileUpdate = {
  company: string | null;
  territory_states: string[];
  categories: string[];
  // CRM fields (docs/PRD_SIGNUP_CRM.md Phase 2). full_name/lead_source are
  // sourced from the signed-in user's own auth state/current page, not
  // typed by hand -- see ProfileCaptureModal/AuthSync.
  full_name: string | null;
  phone: string | null;
  role_title: string | null;
  lead_source: string | null;
};

type GetToken = (options?: { template?: string }) => Promise<string | null>;

async function authenticatedFetch(getToken: GetToken, path: string, init?: RequestInit) {
  const token = await getToken({ template: "fastapi_backend" });
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init?.headers ?? {}), Authorization: `Bearer ${token}` },
  });
}

export async function fetchMyProfile(getToken: GetToken): Promise<UserProfile> {
  const res = await authenticatedFetch(getToken, "/v1/me/profile");
  if (!res.ok) throw new Error(`GET /v1/me/profile failed: ${res.status}`);
  return res.json();
}

export async function saveMyProfile(getToken: GetToken, body: UserProfileUpdate): Promise<void> {
  const res = await authenticatedFetch(getToken, "/v1/me/profile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST /v1/me/profile failed: ${res.status}`);
}

// Backs the "Start for free" Google path -- POST /v1/signup already does
// this for the email/password path, so the two signup routes both land on
// the same trial state. Best-effort: called right after a successful
// Google popup, and a failure here shouldn't block the person from using
// the app they just signed into.
export async function startTrial(getToken: GetToken): Promise<void> {
  await authenticatedFetch(getToken, "/v1/me/start-trial", { method: "POST" }).catch(() => {});
}
