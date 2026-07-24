import type { Project } from "./types";

export function formatUsd(value: number | null | undefined): string {
  if (value == null) return "Undisclosed";
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
  if (value == null) return "—";
  return `${new Intl.NumberFormat("en-US").format(value)} SF`;
}

export function formatDate(value: string | undefined): string {
  if (!value) return "—";
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

export function brandMentioned(project: Project, brand: string): boolean {
  const q = brand.trim().toLowerCase();
  if (!q) return false;
  const hay = [
    ...project.mentioned_brands,
    project.description,
    project.name,
    ...project.key_specs,
    project.owner,
    project.architect,
    project.general_contractor,
  ]
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

export function categoryMatch(project: Project, category: string): boolean {
  const q = category.trim().toLowerCase();
  if (!q) return false;
  return project.competitor_watch.some((c) => c.toLowerCase().includes(q));
}
