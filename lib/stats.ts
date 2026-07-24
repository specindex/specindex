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

export function getVisibilitySnapshot(
  projects: Project[],
  brand: string,
  category: string,
) {
  const mentioned = projects.filter((p) => brandMentioned(p, brand));
  const categoryHits = projects.filter((p) => categoryMatch(p, category));
  const opportunities = categoryHits.filter((p) => !brandMentioned(p, brand));
  const rate =
    projects.length === 0
      ? 0
      : Math.round((mentioned.length / projects.length) * 100);
  const categoryRate =
    projects.length === 0
      ? 0
      : Math.round((categoryHits.length / projects.length) * 100);

  return { mentioned, categoryHits, opportunities, rate, categoryRate };
}

export function getStatusesInCorpus(projects: Project[]): string[] {
  return Array.from(new Set(projects.map((p) => p.status))).sort();
}

export function getCountiesInCorpus(projects: Project[]): string[] {
  return Array.from(new Set(projects.map((p) => p.county).filter(Boolean))).sort();
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
