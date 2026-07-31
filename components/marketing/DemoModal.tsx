"use client";

// One shared "Request Demo" form, triggered from any page via useDemoModal()
// instead of every "Request Demo" button linking to an in-page #demo anchor
// (that pattern meant the same form was duplicated as a full-width section
// at the bottom of five separate pages -- homepage, product, how-it-works,
// about, pricing). Mounted once in app/layout.tsx.

import { createContext, useContext, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useFirebaseAuthOptional } from "@/components/FirebaseAuthProvider";
import { getPostHogDistinctId } from "@/components/PostHogProvider";
import { captureAttributionOnce, readAttribution } from "@/lib/attribution";

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

// docs/architecture-2026/03-growth.md §2c: keep ONE shared modal, add a
// `persona` variant prop rather than forking into per-page forms again
// (the modal's own history already documents that mistake -- five
// duplicated full-width sections, one per page, before this component
// existed). persona changes only copy/subhead and rides along as a
// hidden POST field -- not a different field set, not a different
// endpoint. Revisit a true fork only if a persona needs a field the
// others genuinely don't.
export type DemoPersona = "product" | "pricing" | "about" | "general";

const PERSONA_COPY: Record<DemoPersona, { title: string; subhead: string }> = {
  product: {
    title: "See the product",
    subhead: "Tell us your brand and the divisions you sell. We'll walk you through the index live.",
  },
  pricing: {
    title: "Talk pricing",
    subhead: "Tell us your team size and territory, and we'll recommend the right plan.",
  },
  about: {
    title: "Get in touch",
    subhead: "Tell us your brand and the divisions you sell. We come back with real projects from the index, within one business day.",
  },
  general: {
    title: "Request a Demo",
    subhead: "Tell us your brand and the divisions you sell. We come back with real projects from the index, within one business day.",
  },
};

function defaultPersonaFromPath(pathname: string): DemoPersona {
  if (pathname.startsWith("/pricing")) return "pricing";
  if (pathname.startsWith("/about")) return "about";
  if (pathname.startsWith("/product") || pathname.startsWith("/how-it-works")) return "product";
  return "general";
}

type DemoModalContextValue = {
  openDemoModal: (persona?: DemoPersona) => void;
  closeDemoModal: () => void;
};

const DemoModalContext = createContext<DemoModalContextValue | null>(null);

export function useDemoModal(): DemoModalContextValue {
  const ctx = useContext(DemoModalContext);
  if (!ctx) {
    throw new Error("useDemoModal must be used within DemoModalProvider");
  }
  return ctx;
}

export function DemoModalProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [persona, setPersona] = useState<DemoPersona | undefined>(undefined);
  const pathname = usePathname();

  // Captured once, site-wide, on first mount -- not scoped to the modal
  // itself, since a visitor's first-touch UTM params may arrive on any
  // page, long before they ever open Request Demo.
  useEffect(() => {
    captureAttributionOnce();
  }, []);

  return (
    <DemoModalContext.Provider
      value={{
        openDemoModal: (p) => {
          setPersona(p ?? defaultPersonaFromPath(pathname));
          setOpen(true);
        },
        closeDemoModal: () => setOpen(false),
      }}
    >
      {children}
      {open && (
        <DemoRequestModal persona={persona ?? "general"} onClose={() => setOpen(false)} />
      )}
    </DemoModalContext.Provider>
  );
}

function DemoRequestModal({ persona, onClose }: { persona: DemoPersona; onClose: () => void }) {
  const pathname = usePathname();
  const copy = PERSONA_COPY[persona];
  // null whenever Firebase Auth isn't configured, or when the visitor just
  // isn't signed in -- both are the same "no uid to attach" case from this
  // form's perspective (docs/PRD_SIGNUP_CRM.md Section 2.2).
  const auth = useFirebaseAuthOptional();
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    setPending(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/v1/contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: String(data.get("firstName") ?? ""),
          last_name: String(data.get("lastName") ?? ""),
          email: String(data.get("email") ?? ""),
          company: String(data.get("company") ?? ""),
          categories: String(data.get("categories") ?? ""),
          source_path: pathname,
          firebase_uid: auth?.isSignedIn ? (auth.user?.uid ?? null) : null,
          posthog_distinct_id: getPostHogDistinctId(),
          persona,
          ...readAttribution(),
        }),
      });
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      form.reset();
      setSubmitted(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Something went wrong. Please try again."
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 px-4 py-8 overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-labelledby="demo-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl md:p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="demo-modal-title" className="text-lg font-semibold">
              {copy.title}
            </h2>
            <p className="mt-1.5 text-sm text-[var(--color-gray-600)]">{copy.subhead}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="shrink-0 text-[var(--color-gray-400)] hover:text-[var(--color-ink)]"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {submitted ? (
          <p className="mt-5 rounded-md bg-[var(--color-green-light)] px-4 py-3 text-sm text-[var(--color-green)]">
            Thanks — we&apos;ve got your request and will follow up within one business
            day.
          </p>
        ) : (
          <form className="mt-5" onSubmit={handleSubmit}>
            {error ? (
              <p className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>
            ) : null}
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block sm:col-span-1">
                <span className="text-xs font-medium text-[var(--color-gray-600)]">First name</span>
                <input
                  name="firstName"
                  required
                  className="mt-1.5 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </label>
              <label className="block sm:col-span-1">
                <span className="text-xs font-medium text-[var(--color-gray-600)]">Last name</span>
                <input
                  name="lastName"
                  required
                  className="mt-1.5 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="text-xs font-medium text-[var(--color-gray-600)]">Work email</span>
                <input
                  name="email"
                  type="email"
                  required
                  className="mt-1.5 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="text-xs font-medium text-[var(--color-gray-600)]">Company</span>
                <input
                  name="company"
                  required
                  className="mt-1.5 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="text-xs font-medium text-[var(--color-gray-600)]">
                  Product categories you sell
                </span>
                <input
                  name="categories"
                  placeholder="e.g. HVAC, glazing, flooring"
                  className="mt-1.5 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </label>
            </div>
            <button type="submit" disabled={pending} className="btn btn-demo mt-6 w-full disabled:opacity-60">
              {pending ? "Sending…" : "Request Demo"}
            </button>
            <p className="mt-3 text-center text-xs text-[var(--color-gray-400)]">
              Contact us at{" "}
              <a href="mailto:hello@specindex.ai" className="underline hover:text-[var(--color-ink)]">
                hello@specindex.ai
              </a>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
