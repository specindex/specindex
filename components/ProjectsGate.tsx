"use client";

import { CLERK_ENABLED } from "@/components/ClerkProviders";
import { SignInButton, useAuth } from "@clerk/clerk-react";

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
function SignInWall() {
  return (
    <div className="mx-auto max-w-3xl px-5 py-16 md:px-8 md:py-24">
      <div className="card mx-auto max-w-lg p-10 text-center">
        <h2 className="text-section">Sign in to browse the index</h2>
        <p className="mt-3 text-[var(--color-gray-600)]">
          Project data is available to signed-in accounts. It&apos;s free to create one.
        </p>
        <SignInButton mode="modal">
          <button type="button" className="btn btn-demo mt-6">
            Log In
          </button>
        </SignInButton>
      </div>
    </div>
  );
}

function AuthGate({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();
  if (!isLoaded) return null;
  if (!isSignedIn) return <SignInWall />;
  return <>{children}</>;
}

export function ProjectsGate({ children }: { children: React.ReactNode }) {
  if (!CLERK_ENABLED) return <SignInWall />;
  return <AuthGate>{children}</AuthGate>;
}
