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
  is_active: boolean | null;
  last_login_at: string | null;
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

// Read-only "view as customer" admin query path (GET /v1/ops/customer/{uid},
// api/main.py) -- docs/architecture-2026/02-identity-portals.md Phase 4.
// Never mints a session for the viewed user; just returns their profile +
// tracked-pipeline rows for an admin to read.
export type CustomerTrackedProject = {
  stage: string;
  note: string | null;
  created_at: string;
  updated_at: string;
  project_id: string;
  name: string;
  state: string | null;
  status: string;
};

export type CustomerProfile = {
  firebase_uid: string;
  email: string;
  company: string | null;
  territory_states: string[];
  categories: string[];
  full_name: string | null;
  phone: string | null;
  role_title: string | null;
  lead_source: string | null;
  lifecycle_stage: string | null;
  notes: string | null;
  onboarded_at: string | null;
  created_at: string;
  subscription_tier: string;
  is_active: boolean;
};

export async function fetchCustomerDetail(
  getToken: GetToken,
  firebaseUid: string,
): Promise<{ profile: CustomerProfile; tracked_projects: CustomerTrackedProject[] }> {
  const token = await getToken();
  const res = await fetch(`${API_BASE}/v1/ops/customer/${encodeURIComponent(firebaseUid)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 403) throw new Error("not_authorized");
  if (res.status === 404) throw new Error("not_found");
  if (!res.ok) throw new Error(`GET /v1/ops/customer/${firebaseUid} failed: ${res.status}`);
  return res.json();
}

// POST /v1/ops/customer/{uid}/deactivate|reactivate (api/main.py) --
// deactivate also revokes the user's Firebase refresh tokens server-side.
export async function setCustomerActive(
  getToken: GetToken,
  firebaseUid: string,
  active: boolean,
): Promise<void> {
  const token = await getToken();
  const action = active ? "reactivate" : "deactivate";
  const res = await fetch(`${API_BASE}/v1/ops/customer/${encodeURIComponent(firebaseUid)}/${action}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`${action} failed: ${res.status}`);
}
