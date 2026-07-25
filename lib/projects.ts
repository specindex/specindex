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

async function fetchAllProjects(): Promise<Project[]> {
  const all: Project[] = [];
  let offset = 0;

  while (true) {
    const res = await fetch(
      `${API_BASE}/v1/projects?limit=${PAGE_SIZE}&offset=${offset}`,
    );
    if (!res.ok) {
      throw new Error(
        `specindex-api /v1/projects failed: ${res.status} ${res.statusText}`,
      );
    }
    const data = (await res.json()) as ProjectsListResponse;
    all.push(...data.projects);
    offset += PAGE_SIZE;
    if (offset >= data.total) break;
  }

  return all;
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

export async function getProjectById(id: string): Promise<Project | undefined> {
  const projects = await getAllProjects();
  return projects.find((p) => p.id === id);
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
