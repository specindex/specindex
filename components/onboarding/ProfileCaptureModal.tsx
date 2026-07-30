"use client";

import { useEffect, useState } from "react";
import type { UserProfileUpdate } from "@/lib/userProfile";

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

type Facets = { states: string[]; categories: string[] };

export function ProfileCaptureModal({
  initialTerritory,
  initialCategory,
  fullName,
  leadSource,
  onDismiss,
  onSubmit,
}: {
  initialTerritory: string[];
  initialCategory: string;
  // Sourced from the signed-in user's own auth state (Firebase's
  // displayName) and the page they were on at sign-in -- not asked as form
  // fields, see docs/PRD_SIGNUP_CRM.md Section 4 on why these are captured
  // rather than typed.
  fullName: string | null;
  leadSource: string | null;
  onDismiss: () => void;
  onSubmit: (body: UserProfileUpdate) => Promise<void>;
}) {
  const [territory, setTerritory] = useState<string[]>(initialTerritory);
  const [category, setCategory] = useState(initialCategory);
  const [company, setCompany] = useState("");
  const [phone, setPhone] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [facets, setFacets] = useState<Facets>({ states: [], categories: [] });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/v1/projects/facets`)
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled) setFacets({ states: data.states ?? [], categories: data.categories ?? [] });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  function toggleState(code: string) {
    setTerritory((prev) => (prev.includes(code) ? prev.filter((s) => s !== code) : [...prev, code]));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        company: company.trim() || null,
        territory_states: territory,
        categories: category !== "all" ? [category] : [],
        full_name: fullName,
        phone: phone.trim() || null,
        role_title: roleTitle.trim() || null,
        lead_source: leadSource,
      });
    } catch {
      setError("Couldn't save your profile — try again in a moment.");
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="profile-modal-title"
    >
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl md:p-8">
        <h2 id="profile-modal-title" className="text-xl font-semibold tracking-tight text-[var(--color-ink)]">
          Set up your territory
        </h2>
        <p className="mt-1.5 text-sm text-[var(--color-gray-600)]">
          Tell us where you sell and what you make, and every visit to SpecIndex starts pre-filtered
          to the projects that matter to you.
        </p>

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
              Territory
            </label>
            <div className="mt-2 flex max-h-32 flex-wrap gap-1.5 overflow-y-auto">
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

          <div>
            <label
              htmlFor="profile-category"
              className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]"
            >
              Product category
            </label>
            <select
              id="profile-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
            >
              <option value="all">All product categories</option>
              {facets.categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="profile-company"
              className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]"
            >
              Company <span className="normal-case text-[var(--color-gray-400)]">(optional)</span>
            </label>
            <input
              id="profile-company"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="Acme Building Products"
              className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="profile-role"
                className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]"
              >
                Role <span className="normal-case text-[var(--color-gray-400)]">(optional)</span>
              </label>
              <input
                id="profile-role"
                value={roleTitle}
                onChange={(e) => setRoleTitle(e.target.value)}
                placeholder="Territory Manager"
                className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
              />
            </div>
            <div>
              <label
                htmlFor="profile-phone"
                className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]"
              >
                Phone <span className="normal-case text-[var(--color-gray-400)]">(optional)</span>
              </label>
              <input
                id="profile-phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="(555) 555-0123"
                className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
              />
            </div>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex items-center justify-between gap-3 pt-2">
            <button
              type="button"
              onClick={onDismiss}
              className="text-sm font-medium text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
            >
              Skip for now
            </button>
            <button type="submit" disabled={submitting} className="btn btn-primary disabled:opacity-60">
              {submitting ? "Saving…" : "Save & continue"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
