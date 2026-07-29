// Talks to the /v1/me/profile endpoints added in PR 2 (api/main.py,
// db/migrations/021_user_profiles.sql). Every call fetches a fresh token
// via the `fastapi_backend` Clerk JWT template immediately before the
// request -- Clerk session tokens expire in ~60s, so a cached/reused token
// would intermittently 401. The template is what carries the `email`
// claim upsert_my_profile requires (plain default tokens don't include it).

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
};

export type UserProfileUpdate = {
  company: string | null;
  territory_states: string[];
  categories: string[];
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
