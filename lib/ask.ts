// Talks to the Gemini-grounded /v1/projects/{id}/ask and /v1/me/ask
// endpoints (api/main.py). Both answer strictly from real database rows --
// no web search -- so a question outside SpecIndex's own data comes back
// as an honest "we don't have that" rather than a guess. Same
// fresh-token-per-call pattern as lib/userProfile.ts / lib/tracking.ts.

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

type GetToken = (options?: { template?: string }) => Promise<string | null>;

async function authenticatedFetch(getToken: GetToken, path: string, init?: RequestInit) {
  const token = await getToken({ template: "fastapi_backend" });
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init?.headers ?? {}), Authorization: `Bearer ${token}` },
  });
}

export async function askAboutProject(getToken: GetToken, projectId: string, question: string): Promise<string> {
  const res = await authenticatedFetch(getToken, `/v1/projects/${projectId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(`POST /v1/projects/${projectId}/ask failed: ${res.status}`);
  const data = await res.json();
  return data.answer;
}

export async function askAboutMyTerritory(getToken: GetToken, question: string): Promise<string> {
  const res = await authenticatedFetch(getToken, "/v1/me/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(`POST /v1/me/ask failed: ${res.status}`);
  const data = await res.json();
  return data.answer;
}
