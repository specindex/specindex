import type { Project } from "./types";
import { brandMentioned, categoryMatch } from "./format";

export function getTopCounties(projects: Project[], limit = 6): string[] {
  const counts = new Map<string, number>();
  for (const p of projects) {
    if (!p.county) continue;
    counts.set(p.county, (counts.get(p.county) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([county]) => county);
}

/**
 * Stages where product selection is typically still open. "under_construction"
 * is excluded because structure and long-lead equipment are already committed.
 */
const OPEN_STAGES = new Set([
  "planning",
  "design",
  "permitting",
  "bidding",
  "pre_construction",
  "proposed",
  "approved",
]);

export function isStillOpen(project: Project): boolean {
  return OPEN_STAGES.has(project.status);
}

export function getVisibilitySnapshot(
  projects: Project[],
  brand: string,
  category: string,
) {
  const mentioned = projects.filter((p) => brandMentioned(p, brand));
  const categoryHits = projects.filter((p) => categoryMatch(p, category));
  const opportunities = categoryHits.filter((p) => !brandMentioned(p, brand));
  const stillOpen = opportunities.filter(isStillOpen);
  const rate =
    projects.length === 0
      ? 0
      : Math.round((mentioned.length / projects.length) * 100);
  const categoryRate =
    projects.length === 0
      ? 0
      : Math.round((categoryHits.length / projects.length) * 100);

  return { mentioned, categoryHits, opportunities, stillOpen, rate, categoryRate };
}

export function getStatusesInCorpus(projects: Project[]): string[] {
  return Array.from(new Set(projects.map((p) => p.status))).sort();
}

export function getCountiesInCorpus(projects: Project[]): string[] {
  return Array.from(new Set(projects.map((p) => p.county).filter(Boolean))).sort();
}

export function getStatesInCorpus(projects: Project[]): string[] {
  return Array.from(
    new Set(projects.map((p) => p.state ?? "GA").filter(Boolean)),
  ).sort();
}

/** Distinct years from opened_or_announced_date, most recent first. */
export function getYearsInCorpus(projects: Project[]): string[] {
  const years = new Set<string>();
  for (const p of projects) {
    const year = p.opened_or_announced_date?.slice(0, 4);
    if (year && /^\d{4}$/.test(year)) years.add(year);
  }
  return Array.from(years).sort((a, b) => b.localeCompare(a));
}

export function getCountiesForState(projects: Project[], state: string): string[] {
  const code = state.toUpperCase();
  return Array.from(
    new Set(
      projects
        .filter((p) => (p.state ?? "GA").toUpperCase() === code)
        .map((p) => p.county)
        .filter(Boolean),
    ),
  ).sort();
}

export function getCategoriesInCorpus(projects: Project[]): string[] {
  const categories = new Set<string>();
  for (const p of projects) {
    for (const item of p.competitor_watch) {
      categories.add(item);
    }
  }
  return [...categories].sort((a, b) => a.localeCompare(b));
}
