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

export type Top500County = {
  rank: number;
  county: string;
  state: string;
  population: number;
  projects: number;
  projects_in_window: number;
  documents: number;
  status: "covered" | "projects-only" | "none";
};

export type Top500Coverage = {
  generated_at: string;
  window_start: string;
  counties: Top500County[];
  summary: {
    total: number;
    covered: number;
    projects_only: number;
    none: number;
    total_projects_in_window: number;
    total_documents: number;
  };
};

// Read from the repo rather than the API. Unlike county_coverage, this joins
// the Census population ranking to the corpus, and its whole point is to show
// the counties we hold NOTHING for -- which by definition cannot come from an
// endpoint that serves what we already have. Regenerate with
// scripts/compute-top500-coverage.py after a corpus reload.
export async function getTop500(): Promise<Top500Coverage> {
  const { readFile } = await import("node:fs/promises");
  const { join } = await import("node:path");
  const raw = await readFile(join(process.cwd(), "data", "top500-coverage.json"), "utf8");
  return JSON.parse(raw) as Top500Coverage;
}

export async function getQuality(): Promise<StateQuality[]> {
  const res = await fetch(`${API_BASE}/v1/quality`);
  if (!res.ok) {
    throw new Error(`specindex-api /v1/quality failed: ${res.status} ${res.statusText}`);
  }
  const data = (await res.json()) as QualityResponse;
  return data.quality;
}
