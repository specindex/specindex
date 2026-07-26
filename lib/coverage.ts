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
