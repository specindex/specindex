"use client";

import { FIREBASE_AUTH_ENABLED, useFirebaseAuth } from "@/components/FirebaseAuthProvider";
import { SignedInHome } from "./SignedInHome";

// Wraps the existing marketing homepage. Signed-out visitors (the vast
// majority, and 100% of it while Firebase Auth is disabled) see the
// marketing children completely unchanged -- same SSR/SSG output as before
// this component existed, no flash. Only once a real Firebase session is
// confirmed (`isLoaded && isSignedIn`) does it swap to the personalized
// SignedInHome. Deliberately does NOT blank the page while auth state is
// loading -- falls through to marketing content until sign-in is proven, so
// the common case (anonymous visitor) never waits on an auth check that
// doesn't apply to it.
export function HomePageGate({ children }: { children: React.ReactNode }) {
  if (!FIREBASE_AUTH_ENABLED) return <>{children}</>;
  return <Gate>{children}</Gate>;
}

function Gate({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn, isPendingApproval } = useFirebaseAuth();
  // A pending-approval account would otherwise render SignedInHome, which
  // fetches personalized project data that also 403s -- fall back to the
  // normal marketing homepage rather than showing a broken/empty
  // personalized view. (ProjectsGate shows the actual "pending approval"
  // message when they try to browse projects directly.)
  if (isLoaded && isSignedIn && !isPendingApproval) return <SignedInHome />;
  return <>{children}</>;
}
