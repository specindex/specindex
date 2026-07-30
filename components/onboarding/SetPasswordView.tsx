"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  verifyPasswordResetCode,
  confirmPasswordReset,
  signInWithEmailAndPassword,
} from "firebase/auth";
import { auth } from "@/lib/firebase";
import { Logo } from "@/components/Logo";

// Reads Firebase's password-reset action link params (mode=resetPassword,
// oobCode=...) that StartFreeModal.tsx's sendPasswordResetEmail call
// produces. Same page/component serves a genuine "forgot password" reset
// too, if that's ever wired up client-side -- Firebase's action link shape
// is identical either way.
export function SetPasswordView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const oobCode = searchParams.get("oobCode");

  const [email, setEmail] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);
  const [invalid, setInvalid] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!auth || !oobCode) {
      setInvalid(true);
      setChecking(false);
      return;
    }
    verifyPasswordResetCode(auth, oobCode)
      .then((verifiedEmail) => {
        setEmail(verifiedEmail);
        setChecking(false);
      })
      .catch(() => {
        setInvalid(true);
        setChecking(false);
      });
  }, [oobCode]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    if (!auth || !oobCode || !email) return;
    setSubmitting(true);
    try {
      await confirmPasswordReset(auth, oobCode, password);
      // Land the new session directly rather than sending them back to a
      // sign-in screen -- AuthSync (mounted globally) picks up the
      // resulting session on "/" and opens the onboarding capture modal
      // itself, same as a fresh Google sign-in does.
      await signInWithEmailAndPassword(auth, email, password);
      setDone(true);
      setTimeout(() => router.push("/"), 1200);
    } catch {
      setError("Couldn't set your password — try again in a moment.");
      setSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-sm rounded-xl bg-white p-8 shadow-2xl">
      <div className="flex flex-col items-center text-center">
        <div className="flex items-center gap-2">
          <Logo size={26} />
          <span className="text-lg font-semibold tracking-tight text-[var(--color-ink)]">
            SpecIndex
          </span>
        </div>
        <h1 className="mt-5 text-xl font-semibold text-[var(--color-ink)]">
          {done ? "Password set" : "Set your password"}
        </h1>
        <p className="mt-1 text-sm text-[var(--color-gray-600)]">
          {done
            ? "Taking you to SpecIndex…"
            : checking
              ? "Checking your link…"
              : invalid
                ? "This link is invalid or has expired."
                : `Enter a new password for ${email}.`}
        </p>
      </div>

      {!checking && !invalid && !done && (
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div className="relative">
            <label className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
              New password
            </label>
            <input
              required
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2.5 pr-10 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="absolute right-3 top-[34px] text-xs font-medium text-[var(--color-gray-400)] hover:text-[var(--color-ink)]"
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>

          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
              Re-enter new password
            </label>
            <input
              required
              type={showPassword ? "text" : "password"}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2.5 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button type="submit" disabled={submitting} className="btn btn-demo w-full disabled:opacity-60">
            {submitting ? "Setting password…" : "Set password & continue"}
          </button>
        </form>
      )}

      {invalid && (
        <Link href="/" className="btn btn-outline mt-6 block w-full text-center">
          Back to SpecIndex
        </Link>
      )}
    </div>
  );
}
