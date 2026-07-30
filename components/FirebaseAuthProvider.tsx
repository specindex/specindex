"use client";

import { createContext, useContext, useEffect, useState } from "react";
import {
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
  GoogleAuthProvider,
  type User,
} from "firebase/auth";
import { auth, FIREBASE_AUTH_ENABLED } from "@/lib/firebase";
import { AuthSync } from "@/components/onboarding/AuthSync";
import { SignInModal } from "@/components/onboarding/SignInModal";

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
  user: User | null;
  getToken: GetToken;
  signIn: () => Promise<void>;
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

  useEffect(() => {
    if (!auth) return;
    return onAuthStateChanged(auth, (u) => {
      setUser(u);
      setIsLoaded(true);
    });
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

  async function signInWithGoogle(): Promise<void> {
    if (!auth) return;
    setShowSignInModal(false);
    await signInWithPopup(auth, new GoogleAuthProvider());
  }

  async function signOut(): Promise<void> {
    if (!auth) return;
    await firebaseSignOut(auth);
  }

  const value: FirebaseAuthContextValue = { isLoaded, isSignedIn: !!user, user, getToken, signIn, signOut };

  return (
    <FirebaseAuthContext.Provider value={value}>
      {children}
      <AuthSync />
      {showSignInModal && (
        <SignInModal onGoogle={signInWithGoogle} onClose={() => setShowSignInModal(false)} />
      )}
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
