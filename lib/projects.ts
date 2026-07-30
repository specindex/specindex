import type { Project, ProjectCorpus } from "./types";

// Roadmap item #9: site reads from the live specindex-api instead of the
// committed data/national-commercial-projects.json snapshot. This runs at
// `next build` time (Server Components + generateStaticParams), not in the
// browser — the site stays a static export (see next.config.ts), it just
// pulls from Postgres via the API at build time instead of a stale JSON file.
const API_BASE =
  process.env.SPECINDEX_API_URL || "https://specindex-api-gmm6irqe4q-uc.a.run.app";
const PAGE_SIZE = 100;

// Confirmed live 2026-07-29: even after every individual page's own fetch
// logic was bounded/paced, the build kept failing on whichever page
// happened to be generated in the same batch as the others -- each
// function paces ITSELF, but nothing coordinates how many requests ALL of
// them fire at once against the API's small connection pool during
// Next.js's parallel static-generation phase. This process-wide queue caps
// total concurrent requests regardless of how many pages are building at
// the same time, which per-function pacing alone can't do.
// Next.js spawns one static-generation worker PROCESS per CPU core, each
// with its own copy of this module -- this queue only caps concurrency
// WITHIN one process, so the real global ceiling is roughly this number
// times core count. Set low deliberately: 10 cores locally (worse
// contention than GitHub Actions' runners, typically 2-4 cores) still
// keeps the effective global cap in a reasonable range.
const MAX_CONCURRENT_REQUESTS = 2;
let activeRequests = 0;
const requestQueue: Array<() => void> = [];

async function acquireSlot(): Promise<void> {
  if (activeRequests < MAX_CONCURRENT_REQUESTS) {
    activeRequests++;
    return;
  }
  return new Promise((resolve) => {
    requestQueue.push(() => {
      activeRequests++;
      resolve();
    });
  });
}

function releaseSlot(): void {
  activeRequests--;
  const next = requestQueue.shift();
  if (next) next();
}

// Server-side only (this module never runs in the browser -- see the
// roadmap #9 comment above). SPECINDEX_BUILD_TOKEN authorizes `next build`'s
// bulk reads against /v1/projects and /v1/projects/map-points, which now
// require either this or a signed-in Firebase session (api/main.py's
// require_firebase_user_or_build_token). Unset locally is fine -- /v1/stats,
// /v1/projects/facets, and the single-project teaser endpoint stay
// unauthenticated either way, so local dev without the secret still works
// for everything except full project listing.
const BUILD_TOKEN = process.env.SPECINDEX_BUILD_TOKEN || "";

async function limitedFetch(url: string, init?: RequestInit): Promise<Response> {
  await acquireSlot();
  try {
    const headers = BUILD_TOKEN
      ? { ...init?.headers, "X-Build-Token": BUILD_TOKEN }
      : init?.headers;
    return await fetch(url, { ...init, headers });
  } finally {
    releaseSlot();
  }
}

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
//
// Also retries on the fetch() call itself throwing (ECONNRESET etc) --
// confirmed live 2026-07-29 fetching the full ~175K-row corpus for
// /reporting: the connection gets reset partway through the ~1,750
// sequential page requests that takes, which is a network-level failure
// before any response object exists, not a malformed one. The original
// version of this function only retried the latter.
async function fetchPage(offset: number, attempt = 1): Promise<ProjectsListResponse> {
  let res: Response;
  try {
    res = await limitedFetch(`${API_BASE}/v1/projects?limit=${PAGE_SIZE}&offset=${offset}`);
  } catch (e) {
    if (attempt >= 5) {
      throw new Error(`specindex-api /v1/projects fetch failed at offset ${offset}: ${e}`);
    }
    await new Promise((r) => setTimeout(r, 500 * attempt));
    return fetchPage(offset, attempt + 1);
  }
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
    // Public teaser rows (gated: true, see lib/types.ts) omit these scalars
    // entirely rather than sending null, so they'd otherwise be `undefined`
    // at runtime despite the type saying `string`/`number | null`.
    estimated_value_usd: p.estimated_value_usd ?? null,
    square_footage: p.square_footage ?? null,
    owner: p.owner ?? "",
    architect: p.architect ?? "",
    general_contractor: p.general_contractor ?? "",
    open_for: p.open_for ?? "",
    key_specs: p.key_specs ?? [],
    mentioned_brands: p.mentioned_brands ?? [],
    competitor_watch: p.competitor_watch ?? [],
    sources: p.sources ?? [],
    timeline: p.timeline ?? [],
    news: p.news ?? [],
    provenance: p.provenance ?? [],
    score: p.score ?? null,
    document_count: p.document_count ?? 0,
    has_documents: p.has_documents ?? false,
    documents: p.documents ?? [],
    enrichment: p.enrichment ?? {
      executive_brief: [],
      csi_scope: [],
      team: [],
      permit: [],
      contact: [],
      checked_at: null,
    },
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
    // A full corpus is ~1,750 sequential requests at PAGE_SIZE=100 -- confirmed
    // live 2026-07-29 that firing them back-to-back exhausts the API's small
    // connection pool badly enough that retries alone don't reliably recover
    // (repeated ECONNRESET at different offsets across attempts, not one bad
    // page). A small gap between requests, not just retry-on-failure, is what
    // actually fixes sustained pool pressure instead of just papering over it.
    await new Promise((r) => setTimeout(r, 40));
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
  const res = await limitedFetch(`${API_BASE}/v1/projects/${encodeURIComponent(id)}`);
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

// Only the top-scored projects get a real statically-generated HTML page
// (server-rendered JSON-LD/meta tags, best for SEO and sharing) --
// everything else renders client-side via app/projects/view/page.tsx +
// Firebase Hosting's rewrite fallback (see firebase.json). Necessary once
// the corpus passes a few thousand rows: generateStaticParams over the
// FULL corpus made `next build`'s "Collecting page data" phase grind for
// 4+ hours before crashing with a stack overflow at ~175K rows (see
// docs/ROADMAP.md item 44's follow-up) -- and that number is headed to
// 6.5M+, where full static generation isn't slow, it's impossible (no CI
// system builds 6.5M individual HTML files). Static export's actual build
// cost is now O(this limit), not O(corpus size), regardless of how large
// the corpus grows.
export async function getFeaturedProjectIds(count = 200): Promise<string[]> {
  // /v1/projects caps `limit` at 100 (api/main.py: Query(..., le=100)) --
  // paginate to reach `count` instead of requesting it in one shot, which
  // 422s.
  const ids: string[] = [];
  for (let offset = 0; offset < count; offset += 100) {
    const qs = new URLSearchParams({ sort: "score", limit: String(Math.min(100, count - offset)), offset: String(offset) });
    const res = await limitedFetch(`${API_BASE}/v1/projects?${qs}`);
    if (!res.ok) break;
    const data = (await res.json()) as ProjectsListResponse;
    if (!data.projects?.length) break;
    ids.push(...data.projects.map((p) => p.id));
  }
  return ids;
}

// Bounded sample for stats/rollups that genuinely need to inspect project
// fields (brand mentions, CSI divisions, lat/lon) rather than just count
// rows -- there's no cheap SQL aggregate for those yet. A representative
// top-scored sample instead of the full corpus is a stopgap, not the real
// fix (that's dedicated aggregate endpoints, e.g. /v1/stats/brands), but it
// keeps these illustrative homepage/reporting numbers close enough while
// not timing out the build the way fetching all ~175K+ (and climbing
// toward 6.5M+) rows did.
export async function getSampleProjects(count = 2000): Promise<Project[]> {
  const out: Project[] = [];
  for (let offset = 0; offset < count; offset += PAGE_SIZE) {
    const limit = Math.min(PAGE_SIZE, count - offset);
    const res = await limitedFetch(`${API_BASE}/v1/projects?sort=score&limit=${limit}&offset=${offset}`);
    if (!res.ok) break;
    const data = (await res.json()) as ProjectsListResponse;
    if (!data.projects?.length) break;
    out.push(...data.projects.map(normalizeProject));
    if (data.projects.length < limit) break;
  }
  return out;
}

// Reuses /v1/projects' existing count(*)-before-data-query path (see
// api/main.py's list_projects) instead of fetching real rows just to
// discard everything but a length -- `limit=1` still returns the real
// `total` for the filtered set.
export async function getRecentCount(days: number): Promise<number> {
  const res = await limitedFetch(`${API_BASE}/v1/projects?new_since_days=${days}&limit=1`);
  if (!res.ok) return 0;
  const data = (await res.json()) as ProjectsListResponse;
  return data.total ?? 0;
}

// /v1/projects/facets already runs a cheap `SELECT DISTINCT county` --
// exact count, no corpus fetch, unlike deriving it from a sample.
export async function getDistinctCounties(): Promise<string[]> {
  const res = await limitedFetch(`${API_BASE}/v1/projects/facets`);
  if (!res.ok) return [];
  const data = (await res.json()) as { counties?: string[] };
  return data.counties ?? [];
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
  const res = await limitedFetch(`${API_BASE}/v1/stats`);
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
