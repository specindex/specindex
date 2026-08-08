"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FIREBASE_AUTH_ENABLED, useFirebaseAuth } from "@/components/FirebaseAuthProvider";
import {
  fetchCustomerDetail,
  setCustomerActive,
  extendTrial,
  type CustomerProfile,
  type CustomerTrackedProject,
} from "@/lib/crm";

// Same admin sign-in wall pattern as CrmDashboard -- real enforcement is
// server-side (require_role in api/main.py), this is UX only.
function SignInWall({ onSignIn }: { onSignIn: (() => void) | null }) {
  return (
    <div className="card mx-auto max-w-lg p-10 text-center">
      <h2 className="text-section">Sign in to view customer detail</h2>
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

function readUidFromUrl(): string {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("uid") ?? "";
}

export function CustomerDetail() {
  const { getToken, isSignedIn, isLoaded, signIn } = useFirebaseAuth();
  const [uidInput, setUidInput] = useState(readUidFromUrl);
  const [uid, setUid] = useState(readUidFromUrl);
  const [profile, setProfile] = useState<CustomerProfile | null>(null);
  const [tracked, setTracked] = useState<CustomerTrackedProject[]>([]);
  const [error, setError] = useState<"not_authorized" | "not_found" | "other" | null>(null);
  const [loading, setLoading] = useState(false);
  const [togglingActive, setTogglingActive] = useState(false);
  const [extending, setExtending] = useState(false);

  async function handleExtendTrial() {
    if (!profile) return;
    setExtending(true);
    try {
      await extendTrial(getToken, profile.firebase_uid);
      const fresh = await fetchCustomerDetail(getToken, profile.firebase_uid);
      setProfile(fresh.profile);
    } catch {
      setError("other");
    } finally {
      setExtending(false);
    }
  }

  async function handleToggleActive() {
    if (!profile) return;
    setTogglingActive(true);
    try {
      await setCustomerActive(getToken, profile.firebase_uid, !profile.is_active);
      setProfile({ ...profile, is_active: !profile.is_active });
    } catch {
      setError("other");
    } finally {
      setTogglingActive(false);
    }
  }

  useEffect(() => {
    if (!uid || !isSignedIn) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchCustomerDetail(getToken, uid)
      .then((data) => {
        if (cancelled) return;
        setProfile(data.profile);
        setTracked(data.tracked_projects);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof Error && (e.message === "not_authorized" || e.message === "not_found") ? e.message : "other");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [uid, isSignedIn, getToken]);

  if (!FIREBASE_AUTH_ENABLED) return <SignInWall onSignIn={null} />;
  if (!isLoaded) return null;
  if (!isSignedIn) return <SignInWall onSignIn={signIn} />;

  return (
    <div className="space-y-6">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setUid(uidInput.trim());
        }}
        className="card flex flex-wrap items-end gap-3 p-4"
      >
        <label className="flex-1">
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
            Firebase UID (from the CRM contact_key column, for signed-in users)
          </span>
          <input
            value={uidInput}
            onChange={(e) => setUidInput(e.target.value)}
            className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
            placeholder="e.g. aB1cD2eF..."
          />
        </label>
        <button type="submit" className="btn btn-outline">
          Look up
        </button>
        <Link href="/ops/crm/" className="text-sm font-medium text-[var(--color-green)] hover:underline">
          ← Back to CRM
        </Link>
      </form>

      {loading && <p className="text-sm text-[var(--color-gray-600)]">Loading…</p>}
      {error === "not_authorized" && <p className="text-sm text-red-600">Not authorized for this account.</p>}
      {error === "not_found" && <p className="text-sm text-[var(--color-gray-600)]">No profile found for this UID.</p>}
      {error === "other" && <p className="text-sm text-red-600">Failed to load customer detail.</p>}

      {profile && (
        <>
          <div className="card p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">Profile</p>
            <dl className="mt-3 grid grid-cols-2 gap-4 text-sm md:grid-cols-3">
              <div><dt className="text-[var(--color-gray-400)]">Name</dt><dd className="font-medium">{profile.full_name || "—"}</dd></div>
              <div><dt className="text-[var(--color-gray-400)]">Email</dt><dd className="font-medium">{profile.email}</dd></div>
              <div><dt className="text-[var(--color-gray-400)]">Company</dt><dd className="font-medium">{profile.company || "—"}</dd></div>
              <div><dt className="text-[var(--color-gray-400)]">Phone</dt><dd className="font-medium">{profile.phone || "—"}</dd></div>
              <div><dt className="text-[var(--color-gray-400)]">Role</dt><dd className="font-medium">{profile.role_title || "—"}</dd></div>
              <div><dt className="text-[var(--color-gray-400)]">Tier</dt><dd className="font-medium capitalize">{profile.subscription_tier}</dd></div>
              {profile.subscription_tier === "trial" && (
                <div>
                  <dt className="text-[var(--color-gray-400)]">Trial ends</dt>
                  <dd className={`font-medium ${profile.trial_ends_at && new Date(profile.trial_ends_at) < new Date() ? "text-red-600" : ""}`}>
                    {profile.trial_ends_at
                      ? new Date(profile.trial_ends_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })
                      : "—"}
                    {profile.trial_ends_at && new Date(profile.trial_ends_at) < new Date() && " (expired)"}
                  </dd>
                </div>
              )}
              <div><dt className="text-[var(--color-gray-400)]">Lifecycle stage</dt><dd className="font-medium">{profile.lifecycle_stage || "—"}</dd></div>
              <div><dt className="text-[var(--color-gray-400)]">Active</dt><dd className="font-medium">{profile.is_active ? "Yes" : "No — deactivated"}</dd></div>
              <div><dt className="text-[var(--color-gray-400)]">Territory</dt><dd className="font-medium">{profile.territory_states.join(", ") || "—"}</dd></div>
              <div><dt className="text-[var(--color-gray-400)]">Categories</dt><dd className="font-medium">{profile.categories.join(", ") || "—"}</dd></div>
            </dl>
            {profile.notes && (
              <p className="mt-4 text-sm text-[var(--color-gray-600)]">
                <span className="font-semibold text-[var(--color-ink)]">Notes: </span>{profile.notes}
              </p>
            )}
            <button
              type="button"
              onClick={handleToggleActive}
              disabled={togglingActive}
              className={`mt-4 rounded-md border px-3 py-1.5 text-sm font-medium ${
                profile.is_active
                  ? "border-red-200 text-red-600 hover:bg-red-50"
                  : "border-[var(--color-green)] text-[var(--color-green)] hover:bg-[var(--color-green)]/10"
              }`}
            >
              {togglingActive ? "Working…" : profile.is_active ? "Deactivate account" : "Reactivate account"}
            </button>
            {profile.subscription_tier === "trial" && (
              <button
                type="button"
                onClick={handleExtendTrial}
                disabled={extending}
                className="ml-2 mt-4 rounded-md border border-[var(--color-green)] px-3 py-1.5 text-sm font-medium text-[var(--color-green)] hover:bg-[var(--color-green)]/10"
              >
                {extending ? "Working…" : "Extend trial 14 days"}
              </button>
            )}
          </div>

          <div className="card p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
              Tracked pipeline ({tracked.length})
            </p>
            {tracked.length === 0 ? (
              <p className="mt-3 text-sm text-[var(--color-gray-600)]">Nothing tracked yet.</p>
            ) : (
              <ul className="mt-3 divide-y divide-[var(--color-border)]">
                {tracked.map((t) => (
                  <li key={t.project_id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                    <div>
                      <Link href={`/project/${t.project_id}/`} className="font-medium text-[var(--color-green)] hover:underline">
                        {t.name}
                      </Link>
                      <p className="text-xs text-[var(--color-gray-400)]">{t.state} · {t.status}</p>
                    </div>
                    <span className="rounded-full bg-[var(--color-gray-100)] px-2.5 py-1 text-xs font-medium capitalize">
                      {t.stage}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
