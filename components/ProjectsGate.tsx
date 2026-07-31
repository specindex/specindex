"use client";

import { FIREBASE_AUTH_ENABLED, useFirebaseAuth } from "@/components/FirebaseAuthProvider";

// Gates access to live project data behind sign-in. Genuinely enforces the
// gate (not just a UI overlay) because the wrapped children fetch their data
// client-side on mount -- an anonymous visitor never triggers that fetch, so
// no project data reaches the browser at all. Does NOT cover the ~200
// curated project pages pre-rendered at build time via generateStaticParams
// (app/projects/[id]/page.tsx) -- those have real data baked into static
// HTML already served to the client before this component (or any JS) runs,
// so client-side gating there would be theater, not enforcement. Gating
// those requires either dropping SSG for that route (loses SEO on those
// pages) or real server-side auth -- a separate infra decision, not done
// here.
// `onSignIn` controls whether the Log In trigger calls the real Firebase
// signInWithPopup flow or renders a plain disabled-looking notice. Firebase
// (unlike Clerk) ships no prebuilt modal sign-in component, so this passes a
// callback rather than swapping in a vendor component -- the
// FIREBASE_AUTH_ENABLED-false caller path has no provider mounted at all, so
// it must never call useFirebaseAuth(), only render this same visual wall
// with onSignIn={null}.
function SignInWall({ onSignIn }: { onSignIn: (() => void) | null }) {
  return (
    <div className="mx-auto max-w-3xl px-5 py-16 md:px-8 md:py-24">
      <div className="card mx-auto max-w-lg p-10 text-center">
        <h2 className="text-section">Sign in to browse the index</h2>
        <p className="mt-3 text-[var(--color-gray-600)]">
          Project data is available to signed-in accounts. It&apos;s free to create one.
        </p>
        {onSignIn ? (
          <button type="button" onClick={onSignIn} className="btn btn-demo mt-6">
            Log In
          </button>
        ) : (
          <p className="mt-6 text-sm text-[var(--color-gray-400)]">
            Sign-in is temporarily unavailable. Please try again shortly.
          </p>
        )}
      </div>
    </div>
  );
}

function AuthGate({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn, signIn } = useFirebaseAuth();
  if (!isLoaded) return null;
  if (!isSignedIn) return <SignInWall onSignIn={signIn} />;
  return <>{children}</>;
}

export function ProjectsGate({ children }: { children: React.ReactNode }) {
  if (!FIREBASE_AUTH_ENABLED) return <SignInWall onSignIn={null} />;
  return <AuthGate>{children}</AuthGate>;
}
