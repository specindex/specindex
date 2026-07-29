"use client";

import { ClerkProvider } from "@clerk/clerk-react";

// @clerk/clerk-react, not @clerk/nextjs -- this app is output: "export"
// (fully static, deployed as plain files to Firebase Hosting, zero Next.js
// server/middleware runtime). @clerk/nextjs's session handling depends on
// clerkMiddleware() running on a Node server, which never runs here --
// using it would scaffold a middleware.ts that looks like it's doing
// something but silently never executes. @clerk/clerk-react talks to
// Clerk's Frontend API directly from the browser, no server needed.
//
// Missing publishable key renders children un-wrapped with a console
// warning rather than crashing -- a misconfigured preview/PR build
// (env var not set in that environment) degrades to "no auth" instead of
// a blank page.
export function ClerkProviders({ children }: { children: React.ReactNode }) {
  const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

  if (!publishableKey) {
    if (typeof window !== "undefined") {
      console.warn(
        "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is not set -- rendering without Clerk. Sign-in will not be available.",
      );
    }
    return <>{children}</>;
  }

  return <ClerkProvider publishableKey={publishableKey}>{children}</ClerkProvider>;
}
