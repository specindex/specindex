import type { Project } from "./types";
import { projectHaystack, termAppearsIn } from "./format";

export type Coverage = {
  field: string;
  label: string;
  note: string;
  present: number;
  total: number;
  pct: number;
};

function isPopulated(value: unknown): boolean {
  if (value == null) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value as object).length > 0;
  return true;
}

function coverage(
  projects: Project[],
  field: string,
  label: string,
  note: string,
): Coverage {
  const total = projects.length;
  const present = projects.filter((p) =>
    isPopulated((p as unknown as Record<string, unknown>)[field]),
  ).length;
  return {
    field,
    label,
    note,
    present,
    total,
    pct: total === 0 ? 0 : Math.round((present / total) * 100),
  };
}

/**
 * Fields the public index captures today. Percentages are measured, not asserted.
 */
export function getCapturedCoverage(projects: Project[]): Coverage[] {
  return [
    coverage(projects, "county", "Location and county", "Every record is placed to a county."),
    coverage(projects, "sources", "Source citations", "Links back to the filing or article."),
    coverage(projects, "competitor_watch", "Product categories needed", "Which divisions the job will require."),
    coverage(projects, "status", "Project stage", "Planning, permitting, or under construction."),
    coverage(projects, "opened_or_announced_date", "Announced date", "When the project entered the public record."),
    coverage(projects, "owner", "Owner or developer", "Usually named in the permit or announcement."),
    coverage(projects, "mentioned_brands", "Brands named in coverage", "Mostly tenants and owners, rarely manufacturers."),
    coverage(projects, "estimated_value_usd", "Estimated value", "Permit valuation or reported cost."),
    coverage(projects, "square_footage", "Square footage", "Reported inconsistently across jurisdictions."),
    coverage(projects, "architect", "Architect", "Named far less often than the owner."),
    coverage(projects, "general_contractor", "General contractor", "The biggest gap in the public record today."),
  ].sort((a, b) => b.pct - a.pct);
}

/**
 * Fields the paid reporting tier is meant to answer. These are measured against
 * the current corpus, which is why they read zero: the schema does not carry them
 * yet. This is the gap the database is being built to close.
 */
export function getReportingGaps(projects: Project[]): Coverage[] {
  return [
    coverage(projects, "bid_packages", "Bid packages by division", "Scope and bid due dates per CSI division."),
    coverage(projects, "winning_bidder", "Winning bidder", "Which GC or sub actually took the job."),
    coverage(projects, "award_date", "Award date", "When the contract was signed."),
    coverage(projects, "subcontractors", "Subcontractors by trade", "Who installs each division."),
    coverage(projects, "installed_products", "Products installed", "Manufacturer and product, as built."),
    coverage(projects, "substitution_history", "Substitution history", "Who got swapped out, and for whom."),
    coverage(projects, "completion_date", "Completion date", "Closes the loop on the project lifecycle."),
  ];
}

export type NamedCount = { name: string; count: number };

/**
 * General contractors ranked by appearance. Only reads projects that actually
 * name a GC, so callers must surface the sample size alongside it.
 */
export function getGcLeaderboard(
  projects: Project[],
  limit = 8,
): { rows: NamedCount[]; sampleSize: number; distinct: number } {
  const withGc = projects.filter((p) => isPopulated(p.general_contractor));
  const counts = new Map<string, number>();
  for (const p of withGc) {
    // Some permit records pack a joint venture into one field.
    for (const raw of p.general_contractor.split("/")) {
      const name = raw.trim();
      if (!name) continue;
      counts.set(name, (counts.get(name) ?? 0) + 1);
    }
  }
  const rows = [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
    .slice(0, limit);
  return { rows, sampleSize: withGc.length, distinct: counts.size };
}

/** Category keywords covering CRH / Oldcastle's concrete, paving, and site product lines. */
export const CRH_CATEGORY_KEYWORDS = [
  "concrete",
  "paving",
  "precast",
  "tilt-up",
  "tilt-wall",
  "site work",
  "site civil",
  "site utilities",
  "site infrastructure",
  "civil infrastructure",
  "stormwater",
  "drainage",
  "hardscape",
  "masonry",
  "road construction",
  "bridge components",
  "barriers/guardrail",
  "site/landscape",
  "industrial flooring",
  "epoxy",
];

/**
 * Projects whose needed categories overlap a manufacturer's product lines.
 * Counts distinct projects, not category hits, so a project needing both
 * concrete and paving is not double counted.
 */
export function getCategoryBucket(
  projects: Project[],
  keywords: string[],
): { projects: Project[]; byCategory: NamedCount[] } {
  const matched: Project[] = [];
  const byCategory = new Map<string, number>();
  for (const p of projects) {
    let hit = false;
    for (const cat of p.competitor_watch) {
      const c = cat.toLowerCase();
      if (keywords.some((k) => c.includes(k))) {
        hit = true;
        byCategory.set(c, (byCategory.get(c) ?? 0) + 1);
      }
    }
    if (hit) matched.push(p);
  }
  return {
    projects: matched,
    byCategory: [...byCategory.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name)),
  };
}

/** Counts indexed projects naming a term as a whole word. */
export function countMentions(projects: Project[], term: string): number {
  return projects.filter((p) => termAppearsIn(projectHaystack(p), term)).length;
}

/**
 * Distinct projects naming any of the given terms, so a project mentioning two
 * brands from the same parent company counts once.
 */
export function countProjectsNamingAny(
  projects: Project[],
  terms: string[],
): number {
  return projects.filter((p) => {
    const hay = projectHaystack(p);
    return terms.some((t) => termAppearsIn(hay, t));
  }).length;
}
