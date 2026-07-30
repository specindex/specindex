"use client";

import { CLERK_ENABLED } from "@/components/ClerkProviders";
import { useAuth } from "@clerk/clerk-react";
import { SignedInHome } from "./SignedInHome";

// Wraps the existing marketing homepage. Signed-out visitors (the vast
// majority, and 100% of it while Clerk is disabled) see the marketing
// children completely unchanged -- same SSR/SSG output as before this
// component existed, no flash. Only once a real Clerk session is confirmed
// (`isLoaded && isSignedIn`) does it swap to the personalized SignedInHome.
// Deliberately does NOT blank the page while Clerk is loading -- falls
// through to marketing content until sign-in is proven, so the common case
// (anonymous visitor) never waits on an auth check that doesn't apply to it.
export function HomePageGate({ children }: { children: React.ReactNode }) {
  if (!CLERK_ENABLED) return <>{children}</>;
  return <Gate>{children}</Gate>;
}

function Gate({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();
  if (isLoaded && isSignedIn) return <SignedInHome />;
  return <>{children}</>;
}
