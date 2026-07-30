// Talks to GET /v1/ops/crm (api/main.py, db/migrations/026_crm_contacts.sql).
// Admin-gated server-side (require_admin_user) -- this client just needs a
// valid Firebase session; a non-admin signed-in caller gets a 403 the UI
// surfaces as "not authorized", not a silent empty list.

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

export type CrmContact = {
  contact_key: string;
  name: string | null;
  email: string | null;
  company: string | null;
  phone: string | null;
  role_title: string | null;
  territory_states: string[] | null;
  categories: string[] | null;
  lifecycle_stage: string | null;
  lead_source: string | null;
  demo_request_source: string | null;
  demo_requested_at: string | null;
  onboarded_at: string | null;
  notes: string | null;
};

type GetToken = (options?: { template?: string }) => Promise<string | null>;

export async function fetchCrmContacts(getToken: GetToken): Promise<CrmContact[]> {
  const token = await getToken();
  const res = await fetch(`${API_BASE}/v1/ops/crm`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 403) throw new Error("not_authorized");
  if (!res.ok) throw new Error(`GET /v1/ops/crm failed: ${res.status}`);
  const data = await res.json();
  return data.contacts;
}
