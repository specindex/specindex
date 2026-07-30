"use client";

import { useEffect, useState } from "react";
import { useFirebaseAuth } from "@/components/FirebaseAuthProvider";

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

type GetToken = (options?: { template?: string }) => Promise<string | null>;

type OrgMember = {
  id: number;
  email: string;
  role: "owner" | "member";
  invited_at: string;
  joined_at: string | null;
  accepted: boolean;
};

async function authedFetch(getToken: GetToken, path: string, init?: RequestInit) {
  const token = await getToken({ template: "fastapi_backend" });
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init?.headers ?? {}), Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
  });
}

// docs/architecture-2026: Team-tier multi-seat invite/roster (migration
// 039 org_members + /v1/org/* in api/main.py). Only rendered for
// subscription_tier === "team" -- see AccountSettings.tsx.
export function TeamRoster() {
  const { getToken } = useFirebaseAuth();
  const [members, setMembers] = useState<OrgMember[] | null>(null);
  const [email, setEmail] = useState("");
  const [inviting, setInviting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const res = await authedFetch(getToken, "/v1/org/members");
    if (res.ok) {
      const data = await res.json();
      setMembers(data.members);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setInviting(true);
    try {
      const res = await authedFetch(getToken, "/v1/org/invite", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Couldn't send invite");
      }
      setEmail("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't send invite");
    } finally {
      setInviting(false);
    }
  }

  async function handleRemove(id: number) {
    await authedFetch(getToken, `/v1/org/members/${id}`, { method: "DELETE" });
    await refresh();
  }

  return (
    <div className="card space-y-4 p-5">
      <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">Team</p>

      <form onSubmit={handleInvite} className="flex gap-2">
        <input
          type="email"
          required
          placeholder="teammate@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="flex-1 rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
        />
        <button type="submit" disabled={inviting} className="btn btn-demo whitespace-nowrap">
          {inviting ? "Inviting…" : "Invite"}
        </button>
      </form>
      {error && <p className="text-sm text-red-600">{error}</p>}

      {members === null ? (
        <p className="text-sm text-[var(--color-gray-600)]">Loading…</p>
      ) : members.length === 0 ? (
        <p className="text-sm text-[var(--color-gray-600)]">No team members yet.</p>
      ) : (
        <ul className="divide-y divide-[var(--color-border)]">
          {members.map((m) => (
            <li key={m.id} className="flex items-center justify-between py-2 text-sm">
              <div>
                <span className="font-medium">{m.email}</span>{" "}
                <span className="text-[var(--color-gray-400)]">
                  {m.accepted ? "· active" : "· invited, pending"}
                </span>
              </div>
              <button
                type="button"
                onClick={() => handleRemove(m.id)}
                className="text-[var(--color-gray-400)] hover:text-red-600"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
