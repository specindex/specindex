"use client";

import { useEffect, useState } from "react";
import { FIREBASE_AUTH_ENABLED, useFirebaseAuth } from "@/components/FirebaseAuthProvider";
import { fetchMyProfile, saveMyProfile, type UserProfile } from "@/lib/userProfile";

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

type Facets = { states: string[]; categories: string[] };

// docs/architecture-2026 P2: "Add account/settings page to the user
// portal for post-onboarding profile edits." Reuses the exact same
// POST /v1/me/profile endpoint ProfileCaptureModal already writes to
// (upsert covers both first-capture and later edits, per that
// endpoint's own docstring) -- no new backend write path needed, this
// is just a second, always-available entry point to it.
function SignInWall({ onSignIn }: { onSignIn: (() => void) | null }) {
  return (
    <div className="card mx-auto max-w-lg p-10 text-center">
      <h2 className="text-section">Sign in to view your account</h2>
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

const TIER_LABELS: Record<string, string> = {
  free: "Free",
  trial: "Trial",
  pro: "Pro",
  team: "Team",
};

export function AccountSettings() {
  const { getToken, isSignedIn, isLoaded, signIn, user } = useFirebaseAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [facets, setFacets] = useState<Facets>({ states: [], categories: [] });
  const [territory, setTerritory] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [company, setCompany] = useState("");
  const [phone, setPhone] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isSignedIn) return;
    let cancelled = false;
    Promise.all([
      fetchMyProfile(getToken),
      fetch(`${API_BASE}/v1/projects/facets`).then((r) => r.json()),
    ])
      .then(([p, f]) => {
        if (cancelled) return;
        setProfile(p);
        setTerritory(p.territory_states);
        setCategories(p.categories);
        setCompany(p.company ?? "");
        setPhone(p.phone ?? "");
        setRoleTitle(p.role_title ?? "");
        setFacets({ states: f.states ?? [], categories: f.categories ?? [] });
      })
      .catch(() => setError("Couldn't load your account."))
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isSignedIn, getToken]);

  function toggleState(code: string) {
    setTerritory((prev) => (prev.includes(code) ? prev.filter((s) => s !== code) : [...prev, code]));
  }

  function toggleCategory(c: string) {
    setCategories((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await saveMyProfile(getToken, {
        company: company.trim() || null,
        territory_states: territory,
        categories,
        full_name: profile?.full_name ?? user?.displayName ?? null,
        phone: phone.trim() || null,
        role_title: roleTitle.trim() || null,
        lead_source: null,
      });
      setSaved(true);
    } catch {
      setError("Couldn't save your changes — try again in a moment.");
    } finally {
      setSaving(false);
    }
  }

  if (!FIREBASE_AUTH_ENABLED) return <SignInWall onSignIn={null} />;
  if (!isLoaded) return null;
  if (!isSignedIn) return <SignInWall onSignIn={signIn} />;
  if (loading) return <p className="text-sm text-[var(--color-gray-600)]">Loading…</p>;

  return (
    <form onSubmit={handleSave} className="space-y-6">
      <div className="card p-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">Plan</p>
        <p className="mt-2 text-lg font-semibold">
          {profile ? TIER_LABELS[profile.subscription_tier] ?? profile.subscription_tier : "—"}
        </p>
        {profile?.subscription_tier === "free" && (
          <a href="/pricing/" className="mt-2 inline-block text-sm font-medium text-[var(--color-green)] hover:underline">
            Upgrade to Pro →
          </a>
        )}
      </div>

      <div className="card space-y-4 p-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">Profile</p>

        <div>
          <label className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
            Company <span className="normal-case text-[var(--color-gray-400)]">(optional)</span>
          </label>
          <input
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
              Phone <span className="normal-case text-[var(--color-gray-400)]">(optional)</span>
            </label>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
              Role <span className="normal-case text-[var(--color-gray-400)]">(optional)</span>
            </label>
            <input
              value={roleTitle}
              onChange={(e) => setRoleTitle(e.target.value)}
              className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
            />
          </div>
        </div>
      </div>

      <div className="card p-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">Territory</p>
        <div className="mt-3 flex max-h-40 flex-wrap gap-1.5 overflow-y-auto">
          {facets.states.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => toggleState(s)}
              className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                territory.includes(s)
                  ? "border-[var(--color-green)] bg-[var(--color-green)]/10 text-[var(--color-green)]"
                  : "border-[var(--color-border)] text-[var(--color-gray-600)] hover:border-[var(--color-gray-400)]"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="card p-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
          Product categories
        </p>
        <div className="mt-3 flex max-h-40 flex-wrap gap-1.5 overflow-y-auto">
          {facets.categories.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => toggleCategory(c)}
              className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                categories.includes(c)
                  ? "border-[var(--color-green)] bg-[var(--color-green)]/10 text-[var(--color-green)]"
                  : "border-[var(--color-border)] text-[var(--color-gray-600)] hover:border-[var(--color-gray-400)]"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex items-center gap-3">
        <button type="submit" disabled={saving} className="btn btn-demo">
          {saving ? "Saving…" : "Save changes"}
        </button>
        {saved && <span className="text-sm text-[var(--color-green)]">Saved.</span>}
      </div>
    </form>
  );
}
