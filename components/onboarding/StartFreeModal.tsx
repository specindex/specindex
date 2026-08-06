"use client";

import { useState } from "react";
import { sendPasswordResetEmail } from "firebase/auth";
import { auth } from "@/lib/firebase";

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

// "Start for free" signup (matches the requested reference layout: First/
// Last name, Work email, Company, "Start your N-day free trial" CTA).
// POST /v1/signup provisions a real Firebase account (no password) + a
// 14-day-trial user_profiles row; sendPasswordResetEmail then fires
// Firebase's own hosted "set your password" email -- no custom SMTP code
// needed, Firebase delivers it. The link in that email lands on
// app/set-password/page.tsx.
export function StartFreeModal({ onClose }: { onClose: () => void }) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/v1/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          email,
          company,
        }),
      });
      if (!res.ok) throw new Error(await res.text());

      // The API now sends the set-password email itself over our own SMTP and
      // reports whether it succeeded. Firebase's hosted delivery was accepting
      // the request and delivering nothing to iCloud, and because it accepts
      // unconditionally the browser could never tell. `emailed` is a real
      // answer from the server rather than an assumption.
      const data = await res.json().catch(() => ({}) as { emailed?: boolean });
      if (data.emailed) {
        setSent(true);
        return;
      }

      // Fallback for the case where the server could not send. Still better
      // than nothing, but NEVER claim success without attempting a send --
      // `auth` is null whenever the Firebase config is missing, and this used
      // to fall straight through to setSent(true), stranding the user with an
      // account they cannot get into and no reason to suspect it.
      if (!auth) {
        setError(
          "Your account was created, but we couldn't send the set-password email. Contact hello@specindex.ai.",
        );
        return;
      }
      await sendPasswordResetEmail(auth, email, {
        url: `${window.location.origin}/set-password/`,
        handleCodeInApp: true,
      });
      setSent(true);
    } catch {
      setError("Couldn't create your account — try again in a moment.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-sm rounded-xl bg-white p-8 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-4 top-4 text-[var(--color-gray-400)] hover:text-[var(--color-ink)]"
        >
          ✕
        </button>

        {sent ? (
          <div className="py-6 text-center">
            <h2 className="text-xl font-semibold text-[var(--color-ink)]">Check your email</h2>
            <p className="mt-2 text-sm text-[var(--color-gray-600)]">
              We sent a link to <span className="font-medium text-[var(--color-ink)]">{email}</span> to set
              your password and get started.
            </p>
          </div>
        ) : (
          <>
            <div className="text-center">
              <h2 className="text-xl font-bold leading-snug text-[var(--color-ink)]">
                Create your free account
              </h2>
              <div className="mt-3 flex items-center justify-center gap-4 text-xs text-[var(--color-gray-600)]">
                <span>✕ No credit card required</span>
                <span>✓ All features accessible</span>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
                    First name
                  </label>
                  <input
                    required
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    placeholder="Jane"
                    className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
                    Last name
                  </label>
                  <input
                    required
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder="Doe"
                    className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
                  Work email
                </label>
                <input
                  required
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="jane.doe@company.com"
                  className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </div>

              <div>
                <label className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
                  Company name
                </label>
                <input
                  required
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  placeholder="Acme Building Products"
                  className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </div>

              {error && <p className="text-sm text-red-600">{error}</p>}

              <button type="submit" disabled={submitting} className="btn btn-demo w-full disabled:opacity-60">
                {submitting ? "Creating account…" : "Start your 14-day free trial →"}
              </button>

              <p className="text-center text-xs text-[var(--color-gray-400)]">
                By creating your account, you agree to the{" "}
                <a href="/terms/" className="underline hover:text-[var(--color-ink)]">
                  terms of service
                </a>{" "}
                and{" "}
                <a href="/privacy/" className="underline hover:text-[var(--color-ink)]">
                  privacy policy
                </a>
                .
              </p>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
