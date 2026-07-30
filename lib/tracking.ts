// Talks to /v1/me/tracked-projects and /v1/me/saved-views (db/migrations/
// 022_user_tracked_projects.sql, 024_user_saved_views.sql). Same
// fresh-token-per-call pattern as lib/userProfile.ts -- see that file for
// why (short-lived Firebase ID tokens, re-fetched via getIdToken() on every
// call rather than cached).

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

export type TrackedStage = "watching" | "contacted" | "quoted" | "won" | "lost";

export type TrackedProject = {
  project_id: string;
  spx_id: string;
  name: string;
  city: string;
  county: string;
  state: string;
  status: string;
  estimated_value_usd: number | null;
  stage: TrackedStage;
  note: string | null;
  updated_at: string | null;
};

export type SavedView = {
  id: number;
  name: string;
  territory_states: string[];
  categories: string[];
  created_at: string | null;
};

type GetToken = (options?: { template?: string }) => Promise<string | null>;

async function authenticatedFetch(getToken: GetToken, path: string, init?: RequestInit) {
  const token = await getToken({ template: "fastapi_backend" });
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init?.headers ?? {}), Authorization: `Bearer ${token}` },
  });
}

export async function fetchTrackedProjects(getToken: GetToken): Promise<TrackedProject[]> {
  const res = await authenticatedFetch(getToken, "/v1/me/tracked-projects");
  if (!res.ok) throw new Error(`GET /v1/me/tracked-projects failed: ${res.status}`);
  const data = await res.json();
  return data.tracked;
}

export async function upsertTrackedProject(
  getToken: GetToken,
  projectId: string,
  body: { stage: TrackedStage; note: string | null },
): Promise<void> {
  const res = await authenticatedFetch(getToken, `/v1/me/tracked-projects/${projectId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PUT /v1/me/tracked-projects failed: ${res.status}`);
}

export async function untrackProject(getToken: GetToken, projectId: string): Promise<void> {
  const res = await authenticatedFetch(getToken, `/v1/me/tracked-projects/${projectId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`DELETE /v1/me/tracked-projects failed: ${res.status}`);
}

export async function fetchSavedViews(getToken: GetToken): Promise<SavedView[]> {
  const res = await authenticatedFetch(getToken, "/v1/me/saved-views");
  if (!res.ok) throw new Error(`GET /v1/me/saved-views failed: ${res.status}`);
  const data = await res.json();
  return data.views;
}

export async function createSavedView(
  getToken: GetToken,
  body: { name: string; territory_states: string[]; categories: string[] },
): Promise<number> {
  const res = await authenticatedFetch(getToken, "/v1/me/saved-views", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST /v1/me/saved-views failed: ${res.status}`);
  const data = await res.json();
  return data.id;
}

export async function deleteSavedView(getToken: GetToken, id: number): Promise<void> {
  const res = await authenticatedFetch(getToken, `/v1/me/saved-views/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`DELETE /v1/me/saved-views failed: ${res.status}`);
}

// Lets the project detail page show a Prev/Next triage nav when someone
// arrived by clicking through the signed-in Feed, without threading feed
// state through routing. Session-scoped (not localStorage) -- a stale list
// from a previous session shouldn't outlive the tab, and this is purely a
// navigation convenience, not data worth persisting.
const TRIAGE_KEY = "specindex:triage-list";

export type TriageList = { ids: string[]; currentId: string };

export function writeTriageList(ids: string[], currentId: string): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(TRIAGE_KEY, JSON.stringify({ ids, currentId }));
}

export function readTriageList(): TriageList | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(TRIAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed.ids) && typeof parsed.currentId === "string" ? parsed : null;
  } catch {
    return null;
  }
}
