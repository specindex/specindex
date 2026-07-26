export type CoverageEntry = {
  state: string;
  county: string;
  project_count: number;
  sources: string[];
  coverage_type: "deep" | "thin";
  computed_at: string | null;
};

type CoverageResponse = {
  total: number;
  coverage: CoverageEntry[];
};

export type StateSummary = {
  state: string;
  total_us_counties: number | null;
  counties_covered: number;
  counties_uncovered: number | null;
  coverage_pct: number | null;
  deep: number;
  thin: number;
  total_projects: number;
  net_delta: number | null;
};

export type TopProject = {
  id: string;
  name: string;
  status: string;
  estimated_value_usd: number | null;
  opened_or_announced_date: string | null;
};

export type CoverageInsights = {
  state_summary: StateSummary[];
  top_projects_by_county: Record<string, TopProject[]>;
};

export type StateQuality = {
  state: string;
  total_projects: number;
  pct_has_city: number;
  pct_has_value: number;
  pct_has_contractor: number;
  pct_has_date: number;
  freshness_days: number | null;
  computed_at: string | null;
};

type QualityResponse = {
  total: number;
  quality: StateQuality[];
};

// Same build-time-fetch pattern as lib/projects.ts -- this runs at
// `next build`, not in the browser. county_coverage is a reporting table
// refreshed on demand (scripts/compute-county-coverage.py), not updated
// per-request, so baking it in at build time is consistent with how the
// rest of the site already treats corpus data.
const API_BASE =
  process.env.SPECINDEX_API_URL || "https://specindex-api-gmm6irqe4q-uc.a.run.app";

export async function getCoverage(): Promise<CoverageEntry[]> {
  const res = await fetch(`${API_BASE}/v1/coverage`);
  if (!res.ok) {
    throw new Error(`specindex-api /v1/coverage failed: ${res.status} ${res.statusText}`);
  }
  const data = (await res.json()) as CoverageResponse;
  return data.coverage;
}

export async function getCoverageInsights(): Promise<CoverageInsights> {
  const res = await fetch(`${API_BASE}/v1/coverage/insights`);
  if (!res.ok) {
    throw new Error(`specindex-api /v1/coverage/insights failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as CoverageInsights;
}

export async function getQuality(): Promise<StateQuality[]> {
  const res = await fetch(`${API_BASE}/v1/quality`);
  if (!res.ok) {
    throw new Error(`specindex-api /v1/quality failed: ${res.status} ${res.statusText}`);
  }
  const data = (await res.json()) as QualityResponse;
  return data.quality;
}
