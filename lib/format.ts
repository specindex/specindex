import type { Project } from "./types";

export function formatUsd(value: number | null | undefined): string {
  if (value == null) return "Not reported";
  if (value >= 1_000_000_000) {
    return `$${(value / 1_000_000_000).toFixed(value % 1_000_000_000 === 0 ? 0 : 1)}B`;
  }
  if (value >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(value % 1_000_000 === 0 ? 0 : 1)}M`;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatSf(value: number | null | undefined): string {
  if (value == null) return "Not reported";
  return `${new Intl.NumberFormat("en-US").format(value)} SF`;
}

export function formatDate(value: string | undefined): string {
  if (!value) return "Not reported";
  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export function statusLabel(status: string): string {
  return status
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function typeLabel(type: string): string {
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Whole-word match. Substring matching produced false positives that inflated
 * brand counts: "RDI" hit inside "Nordic" and "bollard install".
 */
export function termAppearsIn(haystack: string, term: string): boolean {
  const q = term.trim();
  if (!q) return false;
  return new RegExp(`\\b${escapeRegExp(q)}\\b`, "i").test(haystack);
}

export function projectHaystack(project: Project): string {
  return [
    ...project.mentioned_brands,
    project.description,
    project.name,
    ...project.key_specs,
    project.owner,
    project.architect,
    project.general_contractor,
  ].join(" ");
}

export function brandMentioned(project: Project, brand: string): boolean {
  return termAppearsIn(projectHaystack(project), brand);
}

export function categoryMatch(project: Project, category: string): boolean {
  const q = category.trim().toLowerCase();
  if (!q) return false;
  return project.competitor_watch.some((c) => c.toLowerCase().includes(q));
}

const STATE_NAMES: Record<string, string> = {
  AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California",
  CO: "Colorado", CT: "Connecticut", DE: "Delaware", FL: "Florida", GA: "Georgia",
  HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa",
  KS: "Kansas", KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland",
  MA: "Massachusetts", MI: "Michigan", MN: "Minnesota", MS: "Mississippi", MO: "Missouri",
  MT: "Montana", NE: "Nebraska", NV: "Nevada", NH: "New Hampshire", NJ: "New Jersey",
  NM: "New Mexico", NY: "New York", NC: "North Carolina", ND: "North Dakota", OH: "Ohio",
  OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina",
  SD: "South Dakota", TN: "Tennessee", TX: "Texas", UT: "Utah", VT: "Vermont",
  VA: "Virginia", WA: "Washington", WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming",
};

export function stateName(code: string | undefined): string {
  if (!code) return "Georgia";
  return STATE_NAMES[code.toUpperCase()] ?? code.toUpperCase();
}
