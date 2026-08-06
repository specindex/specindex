"use client";

import { useEffect, useState } from "react";
import type { UserProfileUpdate } from "@/lib/userProfile";

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

type Facets = { states: string[]; categories: string[] };

const LEAD_SOURCES = [
  "LinkedIn",
  "Search Engine",
  "AI Search (ChatGPT, Claude)",
  "Referral / Colleague",
  "Trade Publication",
  "Other",
];

const DRAFT_KEY = "specindex:onboarding-draft";

type Draft = {
  territory: string[];
  category: string;
  company: string;
  phone: string;
  roleTitle: string;
  territoryRefinement: string;
  leadSourceChoice: string;
};

function readDraft(): Partial<Draft> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.sessionStorage.getItem(DRAFT_KEY) ?? "{}");
  } catch {
    return {};
  }
}

// Two-step wizard, same visual polish as the reference design reviewed via
// Gemini (progress dots, one card per step) but SpecIndex's real fields --
// no branding/logo/workspace-color step, since none of that is a SpecIndex
// feature. Step 1 is the mandatory setup form (unchanged fields, still no
// skip); step 2 asks lead_source directly instead of relying only on the
// pathname-based inference AuthSync already computes -- both are kept
// (Gemini review: combine, don't replace). Form state is persisted to
// sessionStorage as the user fills it in, so a refresh/interruption
// mid-flow doesn't lose their progress (Gemini-flagged real risk: the
// biggest abandonment driver in a no-skip flow is interruption, not
// unwillingness).
export function ProfileCaptureModal({
  initialTerritory,
  initialCategory,
  fullName,
  leadSource: inferredLeadSource,
  onSubmit,
}: {
  initialTerritory: string[];
  initialCategory: string;
  // Sourced from the signed-in user's own auth state (Firebase's
  // displayName) and the page they were on at sign-in -- not asked as form
  // fields, see docs/PRD_SIGNUP_CRM.md Section 4 on why these are captured
  // rather than typed. leadSource here is the pathname-based INFERENCE,
  // kept as a secondary signal now that step 2 asks the user directly.
  fullName: string | null;
  leadSource: string | null;
  onSubmit: (body: UserProfileUpdate) => Promise<void>;
}) {
  const draft = readDraft();
  const [step, setStep] = useState<1 | 2>(1);
  const [territory, setTerritory] = useState<string[]>(draft.territory ?? initialTerritory);
  const [category, setCategory] = useState(draft.category ?? initialCategory);
  const [company, setCompany] = useState(draft.company ?? "");
  const [phone, setPhone] = useState(draft.phone ?? "");
  const [roleTitle, setRoleTitle] = useState(draft.roleTitle ?? "");
  const [territoryRefinement, setTerritoryRefinement] = useState(draft.territoryRefinement ?? "");
  const [leadSourceChoice, setLeadSourceChoice] = useState(draft.leadSourceChoice ?? "");
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

  useEffect(() => {
    const d: Draft = { territory, category, company, phone, roleTitle, territoryRefinement, leadSourceChoice };
    window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify(d));
  }, [territory, category, company, phone, roleTitle, territoryRefinement, leadSourceChoice]);

  function toggleState(code: string) {
    setTerritory((prev) => (prev.includes(code) ? prev.filter((s) => s !== code) : [...prev, code]));
  }

  function handleStep1Submit(e: React.FormEvent) {
    e.preventDefault();
    if (!phone.trim()) {
      setError("Phone is required.");
      return;
    }
    if (territory.length === 0) {
      setError("Select at least one state.");
      return;
    }
    setError(null);
    setStep(2);
  }

  async function handleFinish() {
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        company: company.trim() || null,
        territory_states: territory,
        categories: category !== "all" ? [category] : [],
        full_name: fullName,
        phone: phone.trim(),
        role_title: roleTitle.trim() || null,
        territory_refinement: territoryRefinement.trim() || null,
        // Explicit answer is the primary signal; pathname inference is
        // kept alongside it, never discarded.
        lead_source: leadSourceChoice || inferredLeadSource,
        inferred_lead_source: inferredLeadSource,
      });
      window.sessionStorage.removeItem(DRAFT_KEY);
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
        <div className="mb-4 flex justify-center gap-1.5">
          <span
            className={`h-1.5 rounded-full transition-all ${step === 1 ? "w-6 bg-[var(--color-green)]" : "w-1.5 bg-[var(--color-border)]"}`}
          />
          <span
            className={`h-1.5 rounded-full transition-all ${step === 2 ? "w-6 bg-[var(--color-green)]" : "w-1.5 bg-[var(--color-border)]"}`}
          />
        </div>

        {step === 1 ? (
          <>
            <h2
              id="profile-modal-title"
              className="text-xl font-semibold tracking-tight text-[var(--color-ink)]"
            >
              Set up your territory
            </h2>
            <p className="mt-1.5 text-sm text-[var(--color-gray-600)]">
              Tell us where you sell and what you make, and every visit to SpecIndex starts pre-filtered
              to the projects that matter to you.
            </p>

            <form onSubmit={handleStep1Submit} className="mt-5 space-y-4">
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
                  htmlFor="profile-territory-refinement"
                  className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]"
                >
                  Refine your territory{" "}
                  <span className="normal-case text-[var(--color-gray-400)]">(optional)</span>
                </label>
                <input
                  id="profile-territory-refinement"
                  value={territoryRefinement}
                  onChange={(e) => setTerritoryRefinement(e.target.value)}
                  placeholder="Counties, metro areas, or zip codes"
                  className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-green)] focus:ring-1 focus:ring-[var(--color-green)]"
                />
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
                  className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-green)] focus:ring-1 focus:ring-[var(--color-green)]"
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
                    className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-green)] focus:ring-1 focus:ring-[var(--color-green)]"
                  />
                </div>
                <div>
                  <label
                    htmlFor="profile-phone"
                    className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]"
                  >
                    Phone
                  </label>
                  <input
                    id="profile-phone"
                    type="tel"
                    required
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="(555) 555-0123"
                    className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-green)] focus:ring-1 focus:ring-[var(--color-green)]"
                  />
                  <p className="mt-1 text-xs text-[var(--color-gray-400)]">
                    For account support and setup assistance only.
                  </p>
                </div>
              </div>

              {error && <p className="text-sm text-red-600">{error}</p>}

              <div className="flex items-center justify-end gap-3 pt-2">
                <button type="submit" className="btn btn-primary">
                  Continue →
                </button>
              </div>
            </form>
          </>
        ) : (
          <div className="text-center">
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-[var(--color-green-light)] text-[var(--color-green)]">
              ?
            </div>
            <h2 className="mt-3 text-xl font-semibold tracking-tight text-[var(--color-ink)]">
              How did you hear about SpecIndex?
            </h2>
            <p className="mt-1.5 text-sm text-[var(--color-gray-600)]">
              Helps us know what&apos;s working — thanks!
            </p>

            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {LEAD_SOURCES.map((src) => (
                <button
                  key={src}
                  type="button"
                  onClick={() => setLeadSourceChoice(src)}
                  className={`rounded-lg border px-4 py-2.5 text-sm font-medium transition ${
                    leadSourceChoice === src
                      ? "border-[var(--color-green)] bg-[var(--color-green)]/10 text-[var(--color-green)]"
                      : "border-[var(--color-border)] text-[var(--color-ink)] hover:border-[var(--color-gray-400)]"
                  }`}
                >
                  {src}
                </button>
              ))}
            </div>

            {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

            <div className="mt-6 flex items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="text-sm font-medium text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
              >
                ← Back
              </button>
              <button
                type="button"
                onClick={handleFinish}
                disabled={submitting}
                className="btn btn-primary disabled:opacity-60"
              >
                {submitting ? "Saving…" : "Finish setup →"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
