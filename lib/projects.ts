import type { Project, ProjectCorpus } from "./types";

// Roadmap item #9: site reads from the live specindex-api instead of the
// committed data/national-commercial-projects.json snapshot. This runs at
// `next build` time (Server Components + generateStaticParams), not in the
// browser — the site stays a static export (see next.config.ts), it just
// pulls from Postgres via the API at build time instead of a stale JSON file.
const API_BASE =
  process.env.SPECINDEX_API_URL || "https://specindex-api-gmm6irqe4q-uc.a.run.app";
const PAGE_SIZE = 100;

type ProjectsListResponse = {
  total: number;
  limit: number;
  offset: number;
  projects: Project[];
};

// Build-time static generation hits this with many parallel Next.js
// workers, each independently paginating the full corpus -- under that
// load the small Cloud Run API (a deliberately small connection pool, see
// api/main.py's POOL_MAX_CONN comment) occasionally serves a truncated or
// malformed response for one page rather than a clean error, which
// otherwise surfaces later as a cryptic ".length of undefined" deep in
// page rendering. Retrying a bad page here, with validation that it's
// actually shaped like a project list before trusting it, converts that
// into "occasionally slower," not "occasionally broken."
async function fetchPage(offset: number, attempt = 1): Promise<ProjectsListResponse> {
  const res = await fetch(`${API_BASE}/v1/projects?limit=${PAGE_SIZE}&offset=${offset}`);
  if (!res.ok) {
    throw new Error(`specindex-api /v1/projects failed: ${res.status} ${res.statusText}`);
  }
  const data = (await res.json()) as ProjectsListResponse;
  if (!Array.isArray(data.projects) || typeof data.total !== "number") {
    if (attempt >= 4) {
      throw new Error(`specindex-api /v1/projects returned a malformed page at offset ${offset}`);
    }
    await new Promise((r) => setTimeout(r, 500 * attempt));
    return fetchPage(offset, attempt + 1);
  }
  return data;
}

// Defensive normalization at the one choke point every project passes
// through, regardless of exactly why a given API response might be
// missing an array/object field (seen intermittently during large
// static-export builds; the API itself checks out clean against direct
// queries, so this guards against something in the fetch/transport path
// rather than trying to prove a negative there).
function normalizeProject(p: Project): Project {
  return {
    ...p,
    key_specs: p.key_specs ?? [],
    mentioned_brands: p.mentioned_brands ?? [],
    competitor_watch: p.competitor_watch ?? [],
    sources: p.sources ?? [],
    timeline: p.timeline ?? [],
    news: p.news ?? [],
    provenance: p.provenance ?? [],
    score: p.score ?? null,
  };
}

async function fetchAllProjects(): Promise<Project[]> {
  const all: Project[] = [];
  let offset = 0;

  while (true) {
    const data = await fetchPage(offset);
    all.push(...data.projects.map(normalizeProject));
    offset += PAGE_SIZE;
    if (offset >= data.total) break;
  }

  return all;
}

// Single-project fetch, used by the detail page instead of pulling the
// full bulk-paginated cache and filtering for one id. That approach was
// causing real, reproducible bugs under a 27K-page build's heavy parallel
// load: individual projects would occasionally build with null score/
// timeline/news even though the live API had real data for them -- a
// per-row enrichment race during the bulk crawl, not caught by
// fetchPage()'s malformed-page retry (the page itself was validly
// shaped, just one row's enrichment join came back degraded). Hitting
// /v1/projects/{id}} directly avoids the bulk crawl entirely for the one
// place data correctness matters most.
export async function getProject(id: string): Promise<Project | undefined> {
  const res = await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(id)}`);
  if (res.status === 404) return undefined;
  if (!res.ok) {
    throw new Error(`specindex-api /v1/projects/${id} failed: ${res.status} ${res.statusText}`);
  }
  return normalizeProject((await res.json()) as Project);
}

// Memoized per build process so every page/component sharing this module
// triggers only one paginated fetch sequence against the API, not one per call.
let cache: Promise<Project[]> | null = null;

function getAllProjects(): Promise<Project[]> {
  if (!cache) {
    cache = fetchAllProjects();
  }
  return cache;
}

export async function getProjects(): Promise<Project[]> {
  return getAllProjects();
}

export async function getProjectIds(): Promise<string[]> {
  const projects = await getAllProjects();
  return projects.map((p) => p.id);
}

export async function getProjectsByState(state: string): Promise<Project[]> {
  const code = state.toUpperCase();
  const projects = await getAllProjects();
  return projects.filter((p) => (p.state ?? "GA").toUpperCase() === code);
}

// The live API doesn't expose corpus-level metadata (generated_at, geography,
// notes) the way the old static JSON did — those are derived here instead of
// hardcoded, so they stay accurate as the live corpus grows.
type Stats = { total: number; states: number; early_stage: number };

// Cheap aggregate query (a single view, not the full corpus) -- used by
// the /projects header instead of getCorpus(), which requires fetching
// every project just to derive a total/states count. Kept as a build-time
// fetch (not client-side) since it's small and the page shell benefits
// from being pre-rendered even though the actual project list below it is
// now client-fetched and paginated.
export async function getStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/v1/stats`);
  if (!res.ok) {
    throw new Error(`specindex-api /v1/stats failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as Stats;
}

export async function getCorpus(): Promise<ProjectCorpus> {
  const projects = await getAllProjects();

  const states = new Set(projects.map((p) => (p.state ?? "GA").toUpperCase()));

  const ninetyDaysAgo = new Date();
  ninetyDaysAgo.setDate(ninetyDaysAgo.getDate() - 90);
  const openedLast90Days = projects.filter((p) => {
    if (!p.opened_or_announced_date) return false;
    const d = new Date(p.opened_or_announced_date);
    return !Number.isNaN(d.getTime()) && d >= ninetyDaysAgo;
  }).length;

  return {
    generated_at: new Date().toISOString().slice(0, 10),
    geography: "United States",
    projects,
    stats: {
      total: projects.length,
      states: states.size,
      opened_last_90_days: openedLast90Days,
    },
  };
}
