"use client";

import { useEffect, useMemo, useState } from "react";
import { FIREBASE_AUTH_ENABLED, useFirebaseAuth } from "@/components/FirebaseAuthProvider";
import { fetchCrmContacts, type CrmContact } from "@/lib/crm";

// Deliberately does NOT follow the rest of /v1/ops/*'s unauthenticated-but-
// noindex pattern -- this page renders real names/emails/phone numbers, so
// it needs actual sign-in, not just an unlinked URL. See
// docs/PRD_SIGNUP_CRM.md Section 3 for why that distinction matters. The
// real security boundary is server-side (require_admin_user in
// api/main.py); this gate is UX (don't show a broken table to someone who's
// about to get a 403), not the enforcement itself.
function SignInWall({ onSignIn }: { onSignIn: (() => void) | null }) {
  return (
    <div className="card mx-auto max-w-lg p-10 text-center">
      <h2 className="text-section">Sign in to view the CRM</h2>
      <p className="mt-3 text-[var(--color-gray-600)]">Admin access only.</p>
      {onSignIn ? (
        <button type="button" onClick={onSignIn} className="btn btn-demo mt-6">
          Log In
        </button>
      ) : (
        <p className="mt-6 text-sm text-[var(--color-gray-400)]">Sign-in is temporarily unavailable.</p>
      )}
    </div>
  );
}

const STAGE_TONES: Record<string, string> = {
  signed_up: "bg-[var(--color-gray-100)] text-[var(--color-gray-600)]",
  onboarded: "bg-[var(--color-green-light)] text-[var(--color-green)]",
  demo_requested: "bg-amber-50 text-amber-900",
  in_conversation: "bg-amber-50 text-amber-900",
  trialing: "bg-blue-50 text-blue-700",
  paying: "bg-[var(--color-green)] text-white",
  churned: "bg-red-50 text-red-700",
};

function StageBadge({ stage }: { stage: string | null }) {
  if (!stage) return <span className="text-xs text-[var(--color-gray-400)]">—</span>;
  const cls = STAGE_TONES[stage] ?? "bg-[var(--color-gray-100)] text-[var(--color-gray-600)]";
  return (
    <span className={`inline-flex whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {stage.replace("_", " ")}
    </span>
  );
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function CrmTable() {
  const { getToken } = useFirebaseAuth();
  const [contacts, setContacts] = useState<CrmContact[] | null>(null);
  const [error, setError] = useState<"not_authorized" | "other" | null>(null);
  const [query, setQuery] = useState("");
  const [stageFilter, setStageFilter] = useState("all");

  useEffect(() => {
    fetchCrmContacts(getToken)
      .then(setContacts)
      .catch((e: Error) => setError(e.message === "not_authorized" ? "not_authorized" : "other"));
  }, [getToken]);

  const stages = useMemo(() => {
    const set = new Set((contacts ?? []).map((c) => c.lifecycle_stage).filter(Boolean) as string[]);
    return Array.from(set).sort();
  }, [contacts]);

  const filtered = useMemo(() => {
    if (!contacts) return [];
    const q = query.trim().toLowerCase();
    return contacts.filter((c) => {
      if (stageFilter !== "all" && c.lifecycle_stage !== stageFilter) return false;
      if (!q) return true;
      return [c.name, c.email, c.company].some((f) => f?.toLowerCase().includes(q));
    });
  }, [contacts, query, stageFilter]);

  if (error === "not_authorized") {
    return (
      <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-800">
        Signed in, but this account isn&apos;t on the admin allowlist.
      </p>
    );
  }
  if (error === "other") {
    return (
      <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-800">
        Couldn&apos;t load the CRM data — try refreshing.
      </p>
    );
  }
  if (!contacts) {
    return <p className="text-sm text-[var(--color-gray-400)]">Loading…</p>;
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name, email, company…"
          className="w-full max-w-xs rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-green)] focus:ring-1 focus:ring-[var(--color-green)]"
        />
        <select
          value={stageFilter}
          onChange={(e) => setStageFilter(e.target.value)}
          className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
        >
          <option value="all">All stages</option>
          {stages.map((s) => (
            <option key={s} value={s}>
              {s.replace("_", " ")}
            </option>
          ))}
        </select>
        <span className="text-xs text-[var(--color-gray-400)]">
          {filtered.length} of {contacts.length} contact{contacts.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[960px] text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)] text-left">
              <th className="px-3 py-2 font-semibold">Name</th>
              <th className="px-3 py-2 font-semibold">Email</th>
              <th className="px-3 py-2 font-semibold">Company</th>
              <th className="px-3 py-2 font-semibold">Role</th>
              <th className="px-3 py-2 font-semibold">Territory</th>
              <th className="px-3 py-2 font-semibold">Stage</th>
              <th className="px-3 py-2 font-semibold">Status</th>
              <th className="px-3 py-2 font-semibold">Last login</th>
              <th className="px-3 py-2 font-semibold">Source</th>
              <th className="px-3 py-2 font-semibold">Onboarded</th>
              <th className="px-3 py-2 font-semibold">Notes</th>
              <th className="px-3 py-2 font-semibold"></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => (
              <tr key={c.contact_key} className="border-b border-[var(--color-border)] last:border-0">
                <td className="px-3 py-3 font-medium">{c.name || "—"}</td>
                <td className="px-3 py-3 text-[var(--color-gray-600)]">{c.email || "—"}</td>
                <td className="px-3 py-3 text-[var(--color-gray-600)]">{c.company || "—"}</td>
                <td className="px-3 py-3 text-[var(--color-gray-600)]">{c.role_title || "—"}</td>
                <td className="px-3 py-3 text-[var(--color-gray-600)]">
                  {c.territory_states?.length ? c.territory_states.join(", ") : "—"}
                </td>
                <td className="px-3 py-3">
                  <StageBadge stage={c.lifecycle_stage} />
                </td>
                <td className="px-3 py-3">
                  {c.is_active === null ? (
                    <span className="text-xs text-[var(--color-gray-400)]">—</span>
                  ) : c.is_active ? (
                    <span className="inline-flex whitespace-nowrap rounded-full bg-[var(--color-green-light)] px-2 py-0.5 text-xs font-medium text-[var(--color-green)]">
                      active
                    </span>
                  ) : (
                    <span className="inline-flex whitespace-nowrap rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">
                      deactivated
                    </span>
                  )}
                </td>
                <td className="px-3 py-3 text-xs text-[var(--color-gray-400)]">{fmtDate(c.last_login_at)}</td>
                <td className="px-3 py-3 text-xs text-[var(--color-gray-400)]">
                  {c.lead_source || c.demo_request_source || "—"}
                </td>
                <td className="px-3 py-3 text-xs text-[var(--color-gray-400)]">
                  {fmtDate(c.onboarded_at ?? c.demo_requested_at)}
                </td>
                <td className="max-w-[220px] px-3 py-3 text-xs text-[var(--color-gray-600)]">
                  {c.notes || <span className="text-[var(--color-gray-400)]">—</span>}
                </td>
                <td className="px-3 py-3 text-xs">
                  {/* contact_key IS the firebase_uid for a real signed-in
                      user (crm_contacts' COALESCE) -- the synthetic
                      "anon-<md5>" key means this row is a demo-form-only
                      lead with no account to view. */}
                  {!c.contact_key.startsWith("anon-") && (
                    <a
                      href={`/ops/customer/?uid=${encodeURIComponent(c.contact_key)}`}
                      className="font-medium text-[var(--color-green)] hover:underline"
                    >
                      View →
                    </a>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="mt-4 text-sm text-[var(--color-gray-400)]">No contacts match.</p>
        )}
      </div>

      <p className="mt-6 text-xs text-[var(--color-gray-400)]">
        Read-only. Stage/notes updates go straight against Cloud SQL for now (docs/PRD_SIGNUP_CRM.md
        Section 3) — no edit UI here yet.
      </p>
    </div>
  );
}

function Gate() {
  const { isLoaded, isSignedIn, signIn } = useFirebaseAuth();
  if (!isLoaded) return null;
  if (!isSignedIn) return <SignInWall onSignIn={signIn} />;
  return <CrmTable />;
}

export function CrmDashboard() {
  if (!FIREBASE_AUTH_ENABLED) return <SignInWall onSignIn={null} />;
  return <Gate />;
}
