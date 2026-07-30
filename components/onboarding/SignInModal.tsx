"use client";

import { useEffect } from "react";

// Matches the "pick a provider, then sign in" pattern requested from
// concentrate.ai's login modal -- previously signIn() fired Google's popup
// directly with no intermediate screen. Only Google is wired today;
// Microsoft needs the OAuth provider enabled in the Firebase Console
// (Authentication > Sign-in method > Add new provider > Microsoft, backed
// by an Azure AD app registration for the client id/secret) before
// GoogleAuthProvider's Microsoft equivalent (OAuthProvider('microsoft.com'))
// would actually work -- add it here once that's done.
export function SignInModal({
  onGoogle,
  onClose,
}: {
  onGoogle: () => void;
  onClose: () => void;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-sm rounded-lg bg-white p-8 shadow-xl"
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

        <div className="text-center">
          <h2 className="text-section">Sign in to SpecIndex</h2>
          <p className="mt-2 text-sm text-[var(--color-gray-600)]">
            Continue with your Google account to access your territory and tracked projects.
          </p>
        </div>

        <div className="mt-6 flex flex-col gap-3">
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
            title="Coming soon -- ask your admin if you need Microsoft SSO sooner"
            className="flex cursor-not-allowed items-center justify-center gap-3 rounded-md border border-[var(--color-border)] bg-[var(--color-gray-100)] px-4 py-2.5 text-sm font-medium text-[var(--color-gray-400)]"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path fill="#F25022" d="M0 0h7.6v7.6H0z" />
              <path fill="#7FBA00" d="M8.4 0H16v7.6H8.4z" />
              <path fill="#00A4EF" d="M0 8.4h7.6V16H0z" />
              <path fill="#FFB900" d="M8.4 8.4H16V16H8.4z" />
            </svg>
            Continue with Microsoft (coming soon)
          </button>
        </div>
      </div>
    </div>
  );
}
