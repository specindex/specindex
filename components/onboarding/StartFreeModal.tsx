"use client";

import { useState } from "react";
import { sendPasswordResetEmail, signInWithEmailAndPassword } from "firebase/auth";
import { auth } from "@/lib/firebase";

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

// TWO FIELDS, OR ONE GOOGLE CLICK. This asked first name, last name, email
// and company -- four fields -- and then could not sign anyone in, because the
// account was created with a server-generated password and the only way in was
// an email. On 2026-08-05 that email silently failed and every signup was
// stranded with a real account they could not reach.
//
// Now the user picks their own password and is signed in immediately, so email
// is off the critical path entirely. Name is derived from the address local
// part and company from the domain (server-side, skipped for consumer
// domains), which keeps note attribution working in the CRM half of the moat
// without charging a rep two fields for it.
//
// The set-password email still exists for the Google-less, password-less edge
// case; it is no longer the only door.
export function StartFreeModal({ onClose }: { onClose: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Set when the API reports the email already has an account. Kept separate
  // from `error` so this renders as a route forward, not as a red failure.
  const [existingAccount, setExistingAccount] = useState<
    { hasPassword: boolean; google: boolean } | null
  >(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setExistingAccount(null);
    try {
      const res = await fetch(`${API_BASE}/v1/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      // 409 account_exists is NOT a failure -- it is the single most likely
      // thing to happen on a signup form, and the old code lumped it in with
      // "try again in a moment", which is advice that can never work. The user
      // already has an account; the only useful next action is signing in.
      if (res.status === 409) {
        const body = await res.json().catch(() => ({}) as Record<string, unknown>);
        const detail = (body?.detail ?? {}) as {
          code?: string; has_password?: boolean; providers?: string[];
        };
        if (detail.code === "account_exists") {
          setExistingAccount({
            hasPassword: detail.has_password !== false,
            google: (detail.providers ?? []).includes("google.com"),
          });
          setSubmitting(false);
          return;
        }
      }
      if (!res.ok) throw new Error(await res.text());

      // The API now sends the set-password email itself over our own SMTP and
      // reports whether it succeeded. Firebase's hosted delivery was accepting
      // the request and delivering nothing to iCloud, and because it accepts
      // unconditionally the browser could never tell. `emailed` is a real
      // answer from the server rather than an assumption.
      const data = await res
        .json()
        .catch(() => ({}) as { emailed?: boolean; can_sign_in?: boolean });

      // The user chose a password, so sign them in and let them land in the
      // product. No inbox, no waiting, nothing that can fail silently between
      // creating the account and using it.
      if (data.can_sign_in && auth) {
        await signInWithEmailAndPassword(auth, email.trim(), password);
        onClose();
        return;
      }

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
              <div>
                <label className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
                  Work or personal email
                </label>
                <input
                  required
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  autoComplete="email"
                  className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-green)] focus:ring-1 focus:ring-[var(--color-green)]"
                />
              </div>

              <div>
                <label className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
                  Create a password
                </label>
                <div className="relative">
                  <input
                    required
                    minLength={10}
                    type={showPw ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 10 characters"
                    autoComplete="new-password"
                    className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 pr-16 text-sm outline-none focus:border-[var(--color-green)] focus:ring-1 focus:ring-[var(--color-green)]"
                  />
                  {/* A word, not an eye glyph nobody agrees on. Reps work on
                      phones and mistype constantly. */}
                  <button
                    type="button"
                    onClick={() => setShowPw((s) => !s)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 pt-1 text-xs font-semibold text-[var(--color-gray-400)]"
                  >
                    {showPw ? "Hide" : "Show"}
                  </button>
                </div>
                {/* One rule, rendered once, satisfied or not. No meter, and no
                    wall of red on submit. */}
                <p
                  className={`mt-2 text-xs ${
                    password.length >= 10
                      ? "text-[var(--color-green)]"
                      : "text-[var(--color-gray-400)]"
                  }`}
                >
                  {password.length >= 10 ? "✓ " : ""}At least 10 characters
                </p>
              </div>

              {existingAccount && (
                <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm">
                  <p className="font-semibold text-amber-900">
                    You already have an account
                  </p>
                  <p className="mt-1 text-amber-800">
                    {existingAccount.google && !existingAccount.hasPassword
                      ? "This email is registered with Google. Use “Continue with Google” to sign in."
                      : "Sign in with your password, or reset it if you’ve forgotten."}
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      // Global handler the header uses; opens the sign-in modal
                      // with no page navigation, so the address stays typed.
                      window.dispatchEvent(new CustomEvent("specindex:open-signin"));
                    }}
                    className="mt-2 font-semibold text-amber-900 underline"
                  >
                    Sign in instead
                  </button>
                </div>
              )}
              {error && <p className="text-sm text-red-600">{error}</p>}

              <button type="submit" disabled={submitting} className="btn btn-demo w-full disabled:opacity-60">
                {submitting ? "Creating account…" : "Create account →"}
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
