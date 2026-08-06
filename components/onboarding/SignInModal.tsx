"use client";

import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";

// Matches the layout pattern requested (valuecase.io's login screen):
// centered card, wordmark, "Welcome" heading, an email field + Continue as
// the primary action, a divider, then provider buttons below. Only Google
// is wired -- email sign-in has no backend today (would need Firebase's
// Email Link passwordless flow enabled in the Console plus an action URL,
// the same kind of manual setup Microsoft needs) and Microsoft needs the
// OAuth provider enabled in Firebase Console + an Azure AD app
// registration. Both render as real, visible options (not hidden) so the
// screen matches the target design, but stay disabled until that setup
// happens rather than silently failing.
export function SignInModal({
  onGoogle,
  onPassword,
  onReset,
  onClose,
}: {
  onGoogle: () => void;
  onPassword: (email: string, password: string) => Promise<void>;
  onReset: (email: string) => Promise<void>;
  onClose: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  // Firebase codes must never reach a user. One map, so the same failure
  // reads the same way everywhere.
  function humanError(code: string): string {
    if (code.includes("wrong-password") || code.includes("invalid-credential"))
      return "That email and password don't match. Check caps lock.";
    if (code.includes("user-not-found")) return "We don't have an account for that email.";
    if (code.includes("too-many-requests")) return "Too many attempts. Try again in a few minutes.";
    if (code.includes("user-disabled")) return "This account has been disabled. Email hello@specindex.ai.";
    if (code.includes("network")) return "Couldn't reach SpecIndex. Check your connection.";
    if (code.includes("invalid-email")) return "That doesn't look like an email address.";
    return "Something went wrong. Email hello@specindex.ai and we'll sort it.";
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await onPassword(email.trim(), password);
    } catch (e2) {
      setErr(humanError(String((e2 as { code?: string })?.code ?? e2)));
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    if (!email.trim()) return setErr("Enter your email first, then tap Forgot.");
    setErr(null);
    try {
      await onReset(email.trim());
      setSent(true);
    } catch {
      // Deliberately generic: this path must not reveal whether an account
      // exists. Reset is the higher-value target for an attacker.
      setSent(true);
    }
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

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

        <div className="flex flex-col items-center text-center">
          <div className="flex items-center gap-2">
            <Logo size={26} />
            <span className="text-lg font-semibold tracking-tight text-[var(--color-ink)]">
              SpecIndex
            </span>
          </div>
          <h2 className="mt-5 text-xl font-semibold text-[var(--color-ink)]">Welcome</h2>
          <p className="mt-1 text-sm text-[var(--color-gray-600)]">
            Sign in to SpecIndex to continue.
          </p>
        </div>

        <form className="mt-6" onSubmit={submit}>
          <label
            htmlFor="signin-email"
            className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]"
          >
            Email address
          </label>
          <input
            id="signin-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            autoComplete="email"
            className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2.5 text-sm outline-none focus:border-[var(--color-green)] focus:ring-1 focus:ring-[var(--color-green)]"
          />

          {/* One form, both fields, per PRD 3.5. An email-then-password split
              breaks password-manager autofill and adds a round trip for
              nothing at this scale. */}
          <div className="mt-3 flex items-center justify-between">
            <label
              htmlFor="signin-password"
              className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]"
            >
              Password
            </label>
            <button
              type="button"
              onClick={reset}
              className="text-xs font-semibold text-[var(--color-green)] hover:underline"
            >
              Forgot?
            </button>
          </div>
          <div className="relative">
            <input
              id="signin-password"
              type={showPw ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password"
              autoComplete="current-password"
              className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2.5 pr-16 text-sm outline-none focus:border-[var(--color-green)] focus:ring-1 focus:ring-[var(--color-green)]"
            />
            {/* Reps work on phones and mistype constantly. Not optional. */}
            <button
              type="button"
              onClick={() => setShowPw((s) => !s)}
              className="absolute right-3 top-1/2 -translate-y-1/2 pt-1 text-xs font-semibold text-[var(--color-gray-400)]"
            >
              {showPw ? "Hide" : "Show"}
            </button>
          </div>

          {sent && (
            <p className="mt-3 rounded-md bg-[var(--color-green-light)] px-3 py-2 text-xs text-[var(--color-green)]">
              If an account exists for that email, a reset link is on its way.
            </p>
          )}
          {err && <p className="mt-3 text-xs text-red-600">{err}</p>}

          <button
            type="submit"
            disabled={busy || !email.trim() || !password}
            className="mt-3 w-full rounded-md bg-[var(--color-green)] px-4 py-2.5 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:bg-[var(--color-gray-200)] disabled:text-[var(--color-gray-400)]"
          >
            {busy ? "Signing in…" : "Continue"}
          </button>
        </form>

        <div className="my-5 flex items-center gap-3">
          <div className="h-px flex-1 bg-[var(--color-border)]" />
          <span className="text-xs font-medium text-[var(--color-gray-400)]">OR</span>
          <div className="h-px flex-1 bg-[var(--color-border)]" />
        </div>

        <div className="flex flex-col gap-3">
          <button
            type="button"
            onClick={onGoogle}
            className="flex items-center justify-center gap-3 rounded-md border border-[var(--color-border)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--color-ink)] transition hover:border-[var(--color-gray-400)]"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
              <path
                fill="#4285F4"
                d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.71v2.26h2.9c1.7-1.57 2.7-3.87 2.7-6.6Z"
              />
              <path
                fill="#34A853"
                d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.9-2.26c-.8.54-1.84.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.94v2.33A9 9 0 0 0 9 18Z"
              />
              <path
                fill="#FBBC05"
                d="M3.95 10.7A5.4 5.4 0 0 1 3.67 9c0-.59.1-1.17.28-1.7V4.97H.94A9 9 0 0 0 0 9c0 1.45.35 2.83.94 4.03l3.01-2.33Z"
              />
              <path
                fill="#EA4335"
                d="M9 3.58c1.32 0 2.51.46 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .94 4.97l3.01 2.33C4.66 5.17 6.65 3.58 9 3.58Z"
              />
            </svg>
            Continue with Google
          </button>

          <button
            type="button"
            disabled
            title="Coming soon -- ask your admin if you need Microsoft sign-in sooner"
            className="flex cursor-not-allowed items-center justify-center gap-3 rounded-md border border-[var(--color-border)] bg-[var(--color-gray-100)] px-4 py-2.5 text-sm font-medium text-[var(--color-gray-400)]"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path fill="#F25022" d="M0 0h7.6v7.6H0z" />
              <path fill="#7FBA00" d="M8.4 0H16v7.6H8.4z" />
              <path fill="#00A4EF" d="M0 8.4h7.6V16H0z" />
              <path fill="#FFB900" d="M8.4 8.4H16V16H8.4z" />
            </svg>
            Continue with Microsoft
          </button>
        </div>
      </div>
    </div>
  );
}
