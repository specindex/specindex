// First-party, first-touch attribution capture. A Gemini review of the
// growth architecture flagged that relying on a client-side analytics SDK
// (PostHog) alone silently loses 20-35% of attribution data to ad-blockers
// -- exactly the tech-savvy corporate-browser users this ICP skews toward.
// This is deliberately a plain localStorage write with no dependency, so
// it can't be blocked the same way third-party analytics scripts are.
//
// First-touch only: never overwrite once captured, so a visitor's second
// or third visit (direct navigation, no UTM params) doesn't erase the
// campaign that actually brought them here.

const KEY = "specindex:attribution";

export type Attribution = {
  utm_source: string | null;
  utm_medium: string | null;
  utm_campaign: string | null;
  referrer: string | null;
};

export function captureAttributionOnce(): void {
  if (typeof window === "undefined") return;
  if (window.localStorage.getItem(KEY)) return; // already captured -- first touch wins

  const params = new URLSearchParams(window.location.search);
  const attribution: Attribution = {
    utm_source: params.get("utm_source"),
    utm_medium: params.get("utm_medium"),
    utm_campaign: params.get("utm_campaign"),
    referrer: document.referrer || null,
  };

  // Nothing worth capturing (direct navigation, no UTM, no referrer) --
  // don't write an all-null row that would just shadow a real capture on
  // the next page if this ran again.
  if (!attribution.utm_source && !attribution.utm_medium && !attribution.utm_campaign && !attribution.referrer) {
    return;
  }

  window.localStorage.setItem(KEY, JSON.stringify(attribution));
}

export function readAttribution(): Attribution {
  if (typeof window === "undefined") {
    return { utm_source: null, utm_medium: null, utm_campaign: null, referrer: null };
  }
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return { utm_source: null, utm_medium: null, utm_campaign: null, referrer: null };
    return JSON.parse(raw);
  } catch {
    return { utm_source: null, utm_medium: null, utm_campaign: null, referrer: null };
  }
}
