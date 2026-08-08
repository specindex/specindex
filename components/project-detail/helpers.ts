import { formatDate, stateName } from "@/lib/format";
import type { Project, SpecCitation } from "@/lib/types";

export const EMPTY_FACT_VALUES = new Set(["Not reported", "None found yet"]);

// scripts/enrich-project-details.py stores the model name directly in each
// fact's `sources` text (e.g. "Gemini search grounding, Jul 2026"). Swap the
// vendor label at render time without touching the stored data.
export function displaySource(source: string | null | undefined): string | null {
  if (!source) return source ?? null;
  return source.replace(/\bGemini\b/g, "SpecIndex AI");
}

// TIER 1 physical necessity, TIER 2 declared trades. TIER 3 (brand, material,
// grade) is never derived -- see docs/handoff note on scope derivation.
export type DerivedScope = { division: string; label: string; because: string; tier: 1 | 2 };

const TRADE_TO_DIVISION: Record<string, { division: string; label: string }> = {
  hvac: { division: "23", label: "Heating, ventilating & air conditioning" },
  roofing: { division: "07", label: "Thermal & moisture protection" },
  lighting: { division: "26", label: "Electrical & lighting" },
  electrical: { division: "26", label: "Electrical & lighting" },
  flooring: { division: "09", label: "Finishes" },
  "fire suppression": { division: "21", label: "Fire suppression" },
  plumbing: { division: "22", label: "Plumbing" },
  openings: { division: "08", label: "Openings" },
};

const SCOPE_IMPLICATIONS: { match: RegExp; division: string; label: string; because: string }[] = [
  {
    match: /radiopharmac|theranostic|nuclear medicine|cyclotron/i,
    division: "13 49 00",
    label: "Radiation protection",
    because: "Radiopharmacy and isotope handling require shielded assemblies",
  },
  {
    match: /imaging|\bMRI\b|\bCT\b|radiolog/i,
    division: "21 22 00",
    label: "Clean-agent fire suppression",
    because: "Imaging equipment cannot be protected with water-based suppression",
  },
  {
    match: /cleanroom|clean room|laborator|\blab\b/i,
    division: "23 00 00",
    label: "Controlled-environment HVAC",
    because: "Controlled environments require pressure regimes and filtration",
  },
];

export function deriveScope(description: string, watch: string[]): DerivedScope[] {
  const out: DerivedScope[] = [];
  const seen = new Set<string>();
  const divisionOf = (code: string) => code.trim().split(/\s+/)[0];

  for (const imp of SCOPE_IMPLICATIONS) {
    const div = divisionOf(imp.division);
    if (imp.match.test(description) && !seen.has(div)) {
      seen.add(div);
      out.push({ division: imp.division, label: imp.label, because: imp.because, tier: 1 });
    }
  }
  for (const w of watch) {
    const m = TRADE_TO_DIVISION[w.toLowerCase().trim()];
    if (m && !seen.has(divisionOf(m.division))) {
      seen.add(divisionOf(m.division));
      out.push({ ...m, because: "Named in the source record's trade list", tier: 2 });
    }
  }
  return out;
}

export function scoreTier(total: number) {
  if (total >= 70) {
    return { label: "High priority", tone: "high" as const };
  }
  if (total >= 40) {
    return { label: "Watch", tone: "watch" as const };
  }
  return { label: "Low signal", tone: "low" as const };
}

export function findTeamFact(project: Project, keyPrefix: string) {
  return project.enrichment?.team.find(
    (f) => f.field_key === keyPrefix || f.field_key.startsWith(`${keyPrefix}_`),
  );
}

const TIMELINE_EVENT_LABELS: Record<string, string> = {
  Announced: "Announced",
  Design_Started: "Design started",
  Permit_Issued: "Permit issued",
  Bid_Opened: "Bid opened",
  Awarded: "Awarded",
  Groundbroken: "Groundbroken",
};

export type FeedItem = {
  id: string;
  type: "AI_SIGNAL" | "NEWS";
  source: string;
  time: string;
  title: string;
  url?: string | null;
  body?: string | null;
};

export function buildFeedItems(project: Project): FeedItem[] {
  const signals: FeedItem[] = [
    ...project.timeline.map((t, i) => ({
      id: `timeline-${i}-${t.event_type}`,
      type: "AI_SIGNAL" as const,
      source: t.source_name,
      time: formatDate(t.event_date ?? undefined),
      title: TIMELINE_EVENT_LABELS[t.event_type] ?? t.event_type,
      url: t.source_url,
      body: null,
    })),
    ...(project.enrichment?.permit ?? []).map((f) => ({
      id: `permit-${f.field_key}`,
      type: "AI_SIGNAL" as const,
      source: "Permit filing",
      time: "",
      title: f.label,
      url: null,
      body: f.value,
    })),
  ];
  const news: FeedItem[] = project.news.map((n) => ({
    id: `news-${n.url}`,
    type: "NEWS" as const,
    source: n.source_name ?? "News",
    time: n.published_at ? formatDate(n.published_at.slice(0, 10)) : "",
    title: n.title,
    url: n.url,
    body: null,
  }));
  return [...signals, ...news];
}

export function locationLine(project: { city?: string | null; county?: string | null; state?: string | null }): string {
  return [
    project.city?.trim() || null,
    project.county?.trim() ? `${project.county.trim()} County` : null,
    project.state?.trim() ? stateName(project.state) : null,
  ]
    .filter(Boolean)
    .join(", ");
}

// Doc's six-badge legend. `ruling` is the only field the pipeline emits, so
// the richer badges (basis of design, acceptable manufacturer, fabricator)
// are display-only refinements of the same three underlying rulings -- never
// invented from anything beyond `ruling` + `quoted_text`.
export type CitationPosition = {
  label: string;
  hint: string;
  tone: "green" | "grey" | "amber";
};

export function citationPosition(c: SpecCitation): CitationPosition | null {
  if (!c.ruling) return null;
  if (c.ruling === "proprietary") {
    return c.quoted_text?.toLowerCase().includes("fabricat")
      ? { label: "Fabricator", hint: "Named to fabricate the assembly, hardest to displace", tone: "amber" }
      : { label: "Basis of design", hint: "Product the section was drawn around", tone: "grey" };
  }
  if (c.ruling === "or-equal") {
    return { label: "Open to equals", hint: "Section names alternates and permits substitution", tone: "green" };
  }
  if (c.ruling === "performance") {
    return { label: "Performance spec", hint: "Requirements only, no product named", tone: "grey" };
  }
  return null;
}
