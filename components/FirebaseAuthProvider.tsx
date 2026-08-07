"use client";

import { createContext, useContext, useEffect, useState } from "react";
import {
  onAuthStateChanged,
  signInWithPopup,
  signInWithEmailAndPassword,
  sendPasswordResetEmail,
  signOut as firebaseSignOut,
  GoogleAuthProvider,
  type User,
} from "firebase/auth";
import { auth, FIREBASE_AUTH_ENABLED } from "@/lib/firebase";
import { AuthSync } from "@/components/onboarding/AuthSync";
import { SignInModal } from "@/components/onboarding/SignInModal";
import { StartFreeModal } from "@/components/onboarding/StartFreeModal";
import { startTrial } from "@/lib/userProfile";

// Replaces components/ClerkProviders.tsx. Same reasoning carries over: this
// site is a fully static Next.js export with no Node server, so a
// client-only auth SDK talking directly to the identity provider from the
// browser is required, not a nice-to-have -- Firebase Auth's client SDK
// (firebase/auth) fits that exactly, same as @clerk/clerk-react did before it.
//
// FIREBASE_AUTH_ENABLED is re-exported so client components that need auth
// state (SiteHeader, ProjectsGate, ProjectDetailView, HomePageGate) can gate
// on it before calling useFirebaseAuth() -- calling the hook outside this
// provider throws, so when config is missing those components must render
// their signed-out fallback UI directly rather than mount-and-crash.
export { FIREBASE_AUTH_ENABLED };

type GetToken = (options?: { template?: string }) => Promise<string | null>;

type FirebaseAuthContextValue = {
  isLoaded: boolean;
  isSignedIn: boolean;
  // True once AuthSync's post-sign-in profile fetch comes back 403 --
  // signed in with a valid Firebase session, but user_profiles.is_active
  // is false (new accounts default to this since 2026-08-01, pending
  // manual admin approval). Gated views (ProjectsGate) use this to show a
  // "pending approval" message instead of trying to fetch data that will
  // also 403, or silently showing nothing.
  isPendingApproval: boolean;
  user: User | null;
  getToken: GetToken;
  signIn: () => Promise<void>;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  sendReset: (email: string) => Promise<void>;
  openStartFree: () => void;
  signOut: () => Promise<void>;
};

const FirebaseAuthContext = createContext<FirebaseAuthContextValue | null>(null);

// Throws outside <FirebaseAuthProvider> on purpose -- same contract Clerk's
// useAuth()/useUser() had, so every existing call site (SignedInHome.tsx,
// ProjectDetailView.tsx, etc.) that assumed "if this renders, auth is ready"
// keeps behaving the same way after the swap.
export function useFirebaseAuth(): FirebaseAuthContextValue {
  const ctx = useContext(FirebaseAuthContext);
  if (!ctx) {
    throw new Error("useFirebaseAuth() must be used within <FirebaseAuthProvider>");
  }
  return ctx;
}

// Non-throwing variant for call sites that render regardless of whether
// Firebase Auth is configured (e.g. DemoModal.tsx, mounted globally in
// app/layout.tsx, not behind a FIREBASE_AUTH_ENABLED-gated branch like
// SiteHeader's auth-aware subtree is) -- FirebaseAuthProvider renders
// children with no context at all when config is missing, so useFirebaseAuth()
// would throw there; this returns null instead for "auth isn't available,
// proceed without it" call sites.
export function useFirebaseAuthOptional(): FirebaseAuthContextValue | null {
  return useContext(FirebaseAuthContext);
}

function FirebaseAuthInner({ children }: { children: React.ReactNode }) {
  const [isLoaded, setIsLoaded] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [showSignInModal, setShowSignInModal] = useState(false);
  const [showStartFreeModal, setShowStartFreeModal] = useState(false);
  // Retained under the 2026-08-05 auto-approval policy. Signup no longer sets
  // is_active=false, so this is not a SIGNUP gate any more -- but admin
  // DEACTIVATION still sets is_active=false, and that account must still hit
  // the wall rather than a blank page. Removing the flag would have compiled
  // against the provider and broken ProjectsGate and HomePageGate, which both
  // still read it.
  const [isPendingApproval, setIsPendingApproval] = useState(false);

  useEffect(() => {
    if (!auth) return;
    return onAuthStateChanged(auth, (u) => {
      setUser(u);
      setIsLoaded(true);
      // A sign-out (or switching accounts) must clear a stale pending-
      // approval flag from the previous session -- AuthSync only sets this
      // true, it never clears it itself.
      if (!u) setIsPendingApproval(false);
    });
  }, []);

  // Lets any component ask for the sign-in modal without threading a callback
  // through the tree. StartFreeModal fires this when signup returns 409
  // account_exists, so "Sign in instead" is one click from the error rather
  // than a page navigation that loses what the user typed.
  useEffect(() => {
    const open = () => {
      setShowStartFreeModal(false);
      setShowSignInModal(true);
    };
    window.addEventListener("specindex:open-signin", open);
    return () => window.removeEventListener("specindex:open-signin", open);
  }, []);

  // Ignores `options.template` -- Firebase ID tokens carry the email claim
  // natively, unlike Clerk, which needed a JWT Template configured in the
  // Dashboard to add one. Kept the same call signature the old Clerk-backed
  // getToken had purely so lib/userProfile.ts, lib/tracking.ts, lib/ask.ts,
  // and every call site in SignedInHome.tsx/ProjectDetailView.tsx didn't
  // need to change at all.
  async function getToken(): Promise<string | null> {
    if (!auth?.currentUser) return null;
    return auth.currentUser.getIdToken();
  }

  // Opens the provider-choice modal instead of firing Google's popup
  // directly -- every existing call site (SiteHeader, the various
  // SignInWall components) just calls signIn(), so this change alone gives
  // all of them the new modal for free, no call-site updates needed.
  async function signIn(): Promise<void> {
    setShowSignInModal(true);
  }

  // Email + password sign-in. The modal's Continue button was hardcoded
  // `disabled` with the note "email sign-in has no backend today... would need
  // Firebase's Email Link passwordless flow enabled in the Console". That
  // reasoning was true when written and is now stale: email/password was
  // enabled in the console on 2026-08-06, and it is simpler than the
  // passwordless flow it was waiting on -- no action URL, no link handling.
  //
  // Until then a first-time user could create an account and never log in.
  // Signup worked because the API provisions accounts server-side with the
  // Admin SDK, which bypasses the provider setting entirely, so the door
  // looked open from the outside and was locked from the inside.
  async function signInWithPassword(email: string, password: string): Promise<void> {
    if (!auth) throw new Error("auth unavailable");
    await signInWithEmailAndPassword(auth, email, password);
    setShowSignInModal(false);
  }

  async function sendReset(email: string): Promise<void> {
    if (!auth) throw new Error("auth unavailable");
    // Points at the page that EXISTS. The PRD names /auth/action, but that
    // route 404s today, and sending a reset link to a 404 is worse than not
    // sending one.
    await sendPasswordResetEmail(auth, email, {
      url: `${window.location.origin}/set-password/`,
    });
  }

  async function signInWithGoogle(): Promise<void> {
    if (!auth) return;
    setShowSignInModal(false);
    await signInWithPopup(auth, new GoogleAuthProvider());
    // Unconditional, not tied to which button opened this modal --
    // /v1/me/start-trial only ever upgrades a user who's still on `free`
    // with no prior trial, so this is a safe no-op for every returning
    // user and only actually grants anything the one time it matters: a
    // brand-new Google sign-in, regardless of whether they clicked "Login"
    // or "Start for free" to get here.
    await startTrial(getToken);
  }

  async function signOut(): Promise<void> {
    if (!auth) return;
    await firebaseSignOut(auth);
  }

  const value: FirebaseAuthContextValue = {
    isLoaded,
    isSignedIn: !!user,
    user,
    // Not a signup gate under the 2026-08-05 auto-approval policy -- signup
    // sets is_active=true. Still true for an account an admin DEACTIVATED, so
    // ProjectsGate/HomePageGate show the wall rather than a blank page.
    isPendingApproval,
    getToken,
    signIn,
    signInWithPassword,
    sendReset,
    openStartFree: () => setShowStartFreeModal(true),
    signOut,
  };

  return (
    <FirebaseAuthContext.Provider value={value}>
      {children}
      <AuthSync onPendingApproval={() => setIsPendingApproval(true)} />
      {showSignInModal && (
        <SignInModal
          onGoogle={signInWithGoogle}
          onPassword={signInWithPassword}
          onReset={sendReset}
          onClose={() => setShowSignInModal(false)}
        />
      )}
      {showStartFreeModal && <StartFreeModal onClose={() => setShowStartFreeModal(false)} />}
    </FirebaseAuthContext.Provider>
  );
}

export function FirebaseAuthProvider({ children }: { children: React.ReactNode }) {
  if (!FIREBASE_AUTH_ENABLED) {
    if (typeof window !== "undefined") {
      console.warn(
        "Firebase Auth env vars are not set -- rendering without auth. Sign-in will not be available.",
      );
    }
    return <>{children}</>;
  }
  return <FirebaseAuthInner>{children}</FirebaseAuthInner>;
}
