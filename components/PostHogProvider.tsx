"use client";

import { useEffect } from "react";
import posthog from "posthog-js";

// docs/architecture-2026/03-growth.md: PostHog Cloud (hosted, free tier),
// autocapture on -- the 7 marketing pages need only this snippet, not
// per-element instrumentation, for page-level conversion funnels.
// Deliberately NOT the primary attribution source (see lib/attribution.ts's
// header comment -- ad-blockers silently drop 20-35% of this ICP's
// client-side tracking); this is for session replay/funnels only.
//
// Missing key renders nothing rather than crashing -- same
// "degrades to disabled" pattern as ClerkProviders/FirebaseAuthProvider
// for a preview/PR build that doesn't have the env var set.
export const POSTHOG_ENABLED = !!process.env.NEXT_PUBLIC_POSTHOG_KEY;

let initialized = false;

export function initPostHog(): typeof posthog | null {
  const key = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  if (!key) return null;
  if (!initialized) {
    posthog.init(key, {
      api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com",
      person_profiles: "identified_only",
      // Respect Do Not Track -- growth doc's explicit requirement, not a
      // default posthog-js applies on its own.
      respect_dnt: true,
      capture_pageview: true,
    });
    initialized = true;
  }
  return posthog;
}

export function getPostHogDistinctId(): string | null {
  if (!POSTHOG_ENABLED || !initialized) return null;
  try {
    return posthog.get_distinct_id() ?? null;
  } catch {
    return null;
  }
}

export function PostHogProvider() {
  useEffect(() => {
    initPostHog();
  }, []);

  return null;
}
