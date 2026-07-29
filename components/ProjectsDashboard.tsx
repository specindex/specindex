"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Project } from "@/lib/types";
import { formatDate, formatSf, formatUsd, stateName, typeLabel } from "@/lib/format";
import { StatusPill } from "./StatusPill";
import { ProjectsMapView } from "./ProjectsMapView";
import { PROFILE_SYNC_EVENT, type ProfileSyncDetail } from "@/lib/userProfile";

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";
const PAGE_SIZE = 50;
const TERRITORY_KEY = "specindex:territory";
const CATEGORY_KEY = "specindex:category";
const ONBOARDED_KEY = "specindex:onboarded";

type Facets = {
  states: string[];
  counties: string[];
  project_types: string[];
  statuses: string[];
  categories: string[];
  years: number[];
};

type SortKey = "score" | "name" | "value" | "recency";

// Mirrors compute-project-documents.py's DOCUMENT_TYPE_KEYWORDS categories.
const DOCUMENT_TYPES: { value: string; label: string }[] = [
  { value: "specifications", label: "Specifications" },
  { value: "drawings_plans", label: "Drawings & Plans" },
  { value: "structural_engineering", label: "Structural / Engineering" },
  { value: "staff_report", label: "Staff Report" },
  { value: "meeting_agenda", label: "Meeting Agenda" },
  { value: "permit_application", label: "Permit Application" },
  { value: "other", label: "Other" },
];

const EMPTY_FACETS: Facets = {
  states: [],
  counties: [],
  project_types: [],
  statuses: [],
  categories: [],
  years: [],
};

export function buildQuery(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "" && v !== "all") usp.set(k, String(v));
  }
  return usp.toString();
}

// SSR-safe: these components render on the client only ("use client"), but
// guard against `window`/`localStorage` being unavailable during the
// initial static-export prerender pass anyway.
function readStoredList(key: string): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function readStoredValue(key: string): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(key);
}

export function ProjectsDashboard() {
  // Restored from localStorage so a returning visitor lands straight on
  // their territory+category instead of the full nationwide list every
  // time -- a lightweight stand-in for a saved profile until real
  // accounts exist (see docs/ROADMAP.md item 46, Phase B).
  const [territory, setTerritory] = useState<string[]>(() => readStoredList(TERRITORY_KEY));
  const [status, setStatus] = useState("all");
  const [projectType, setProjectType] = useState("all");
  const [county, setCounty] = useState("all");
  const [category, setCategory] = useState(() => readStoredValue(CATEGORY_KEY) ?? "all");
  const [year, setYear] = useState("all");
  const [hasDocuments, setHasDocuments] = useState("all"); // "all" | "yes" | "no"
  const [documentType, setDocumentType] = useState("all"); // "all" | one of DOCUMENT_TYPES below
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("score");
  const [offset, setOffset] = useState(0);
  const [newOnly, setNewOnly] = useState(false);
  const [newThisWeek, setNewThisWeek] = useState<number | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [view, setView] = useState<"list" | "map">("list");

  const [facets, setFacets] = useState<Facets>(EMPTY_FACETS);
  const [projects, setProjects] = useState<Project[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // First-time visitor with no saved territory/category -- nudge them to
  // set one instead of defaulting silently to a nationwide, unranked-feeling
  // list. Dismissing (or just picking a state/category) hides it for good.
  useEffect(() => {
    if (territory.length === 0 && category === "all" && !localStorage.getItem(ONBOARDED_KEY)) {
      setShowOnboarding(true);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    localStorage.setItem(TERRITORY_KEY, JSON.stringify(territory));
  }, [territory]);

  useEffect(() => {
    localStorage.setItem(CATEGORY_KEY, category);
  }, [category]);

  function dismissOnboarding() {
    localStorage.setItem(ONBOARDED_KEY, "1");
    setShowOnboarding(false);
  }

  // A signed-in visitor's server profile (AuthSync.tsx) is the source of
  // truth once it loads -- but if this dashboard is already mounted (e.g.
  // sign-in happened via the header modal while already on /projects/), the
  // territory/category state above was already initialized from whatever
  // localStorage held at mount time and won't otherwise notice the change:
  // the `storage` event only fires in *other* tabs, never this one.
  useEffect(() => {
    function onProfileSync(e: Event) {
      const { territory: t, category: c } = (e as CustomEvent<ProfileSyncDetail>).detail;
      setTerritory(t);
      setCategory(c);
      dismissOnboarding();
    }
    window.addEventListener(PROFILE_SYNC_EVENT, onProfileSync);
    return () => window.removeEventListener(PROFILE_SYNC_EVENT, onProfileSync);
  }, []);

  // Lightweight separate fetch for the "N new this week" count so it's
  // visible in the header regardless of whether the newOnly toggle is on,
  // scoped to the visitor's current territory (not the whole corpus).
  useEffect(() => {
    let cancelled = false;
    const qs = buildQuery({ state: territory.join(","), new_since_days: 7, limit: 1 });
    fetch(`${API_BASE}/v1/projects?${qs}`)
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled) setNewThisWeek(typeof data.total === "number" ? data.total : null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [territory]);

  // Debounce free-text search so every keystroke doesn't fire a request.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  // Any filter change resets to page 1.
  const filterKey = JSON.stringify([territory, status, projectType, county, category, year, hasDocuments, documentType, debouncedQuery, sort, newOnly]);
  const prevFilterKey = useRef(filterKey);
  useEffect(() => {
    if (prevFilterKey.current !== filterKey) {
      prevFilterKey.current = filterKey;
      setOffset(0);
    }
  }, [filterKey]);

  // Facets refetch when territory changes (county list narrows to the
  // selected state(s), matching the old client-side-filtered UI's
  // per-state county narrowing).
  useEffect(() => {
    let cancelled = false;
    const qs = buildQuery({ state: territory.join(",") });
    fetch(`${API_BASE}/v1/projects/facets${qs ? `?${qs}` : ""}`)
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled) setFacets(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [territory]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const qs = buildQuery({
      state: territory.join(","),
      status,
      project_type: projectType,
      county,
      category,
      year,
      has_documents: hasDocuments === "all" ? undefined : hasDocuments === "yes" ? "true" : "false",
      document_type: documentType === "all" ? undefined : documentType,
      q: debouncedQuery,
      sort,
      new_since_days: newOnly ? 7 : undefined,
      limit: PAGE_SIZE,
      offset,
    });
    fetch(`${API_BASE}/v1/projects?${qs}`)
      .then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (cancelled) return;
        setProjects(data.projects ?? []);
        setTotal(data.total ?? 0);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load projects");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [territory, status, projectType, county, category, year, hasDocuments, documentType, debouncedQuery, sort, newOnly, offset]);

  const territoryLabel = useMemo(() => {
    if (territory.length === 0) return "All states";
    if (territory.length <= 3) return territory.join(", ");
    return `${territory.length} states`;
  }, [territory]);

  function toggleState(code: string) {
    setTerritory((prev) => (prev.includes(code) ? prev.filter((s) => s !== code) : [...prev, code]));
  }

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Leads with "top N" framing on the default (score-sorted, page 1) view
  // -- this is a ranked shortlist, not a database dump -- and falls back to
  // a plain match count once someone re-sorts or pages past it.
  const resultsLabel = useMemo(() => {
    if (loading) return "Loading…";
    const scope = territory.length > 0 ? `in ${territoryLabel}` : "nationwide";
    const catLabel = category !== "all" ? ` · ${category}` : "";
    if (sort === "score" && offset === 0 && !newOnly) {
      const shown = Math.min(PAGE_SIZE, total);
      return `Top ${shown} ${scope}${catLabel} · ${total.toLocaleString()} total match — refine below to search all`;
    }
    return `${total.toLocaleString()} projects match ${scope}${catLabel} · page ${page} of ${totalPages}`;
  }, [loading, territory, territoryLabel, category, sort, offset, newOnly, total, page, totalPages]);

  return (
    <div>
      {showOnboarding && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--color-amber)]/30 bg-[var(--color-amber)]/10 px-4 py-3">
          <p className="text-sm text-[var(--color-ink)]">
            Pick your territory and product category below to see the projects that actually need
            what you sell — not all {total.toLocaleString()}.
          </p>
          <button type="button" onClick={dismissOnboarding} className="text-xs font-medium text-[var(--color-gray-600)] hover:text-[var(--color-ink)]">
            Dismiss
          </button>
        </div>
      )}
      <div className="card p-4 md:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <label className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
            Your territory
          </label>
          <div className="flex items-center gap-3">
            {newThisWeek !== null && newThisWeek > 0 && (
              <button
                type="button"
                onClick={() => {
                  setNewOnly((v) => !v);
                  dismissOnboarding();
                }}
                className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                  newOnly
                    ? "border-[var(--color-amber)] bg-[var(--color-amber)]/10 text-[var(--color-amber)]"
                    : "border-[var(--color-border)] text-[var(--color-gray-600)] hover:border-[var(--color-gray-400)]"
                }`}
              >
                🔔 {newThisWeek.toLocaleString()} new this week
              </button>
            )}
            <span className="text-xs text-[var(--color-gray-600)]">{territoryLabel}</span>
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {facets.states.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => {
                toggleState(s);
                dismissOnboarding();
              }}
              className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                territory.includes(s)
                  ? "border-[var(--color-green)] bg-[var(--color-green)]/10 text-[var(--color-green)]"
                  : "border-[var(--color-border)] text-[var(--color-gray-600)] hover:border-[var(--color-gray-400)]"
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="City, owner, GC, HVAC, glazing, healthcare…"
          className="mt-4 w-full rounded-md border border-[var(--color-border)] bg-white px-4 py-3 text-base outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
        />
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-7">
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm">
            <option value="all">All statuses</option>
            {facets.statuses.map((s) => (
              <option key={s} value={s}>{s.replaceAll("_", " ")}</option>
            ))}
          </select>
          <select value={projectType} onChange={(e) => setProjectType(e.target.value)} className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm">
            <option value="all">All types</option>
            {facets.project_types.map((t) => (
              <option key={t} value={t}>{typeLabel(t)}</option>
            ))}
          </select>
          <select value={county} onChange={(e) => setCounty(e.target.value)} className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm">
            <option value="all">All counties</option>
            {facets.counties.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              dismissOnboarding();
            }}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="all">All product categories</option>
            {facets.categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select value={year} onChange={(e) => setYear(e.target.value)} className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm">
            <option value="all">All years</option>
            {facets.years.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm">
            <option value="score">Sort: priority score</option>
            <option value="value">Sort: highest value</option>
            <option value="recency">Sort: most recent</option>
            <option value="name">Sort: name</option>
          </select>
          <select value={hasDocuments} onChange={(e) => setHasDocuments(e.target.value)} className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm">
            <option value="all">Documents: any</option>
            <option value="yes">Has attached documents</option>
            <option value="no">No attached documents</option>
          </select>
          <select value={documentType} onChange={(e) => setDocumentType(e.target.value)} className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm">
            <option value="all">Document type: any</option>
            {DOCUMENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-[var(--color-gray-600)]">{resultsLabel}</p>
          <div className="flex overflow-hidden rounded-md border border-[var(--color-border)] text-xs font-medium">
            <button
              type="button"
              onClick={() => setView("list")}
              className={`px-3 py-1.5 ${view === "list" ? "bg-[var(--color-green)] text-white" : "bg-white text-[var(--color-gray-600)]"}`}
            >
              List
            </button>
            <button
              type="button"
              onClick={() => setView("map")}
              className={`px-3 py-1.5 ${view === "map" ? "bg-[var(--color-green)] text-white" : "bg-white text-[var(--color-gray-600)]"}`}
            >
              Map
            </button>
          </div>
        </div>
      </div>

      {error && <p className="mt-4 text-sm text-red-600">Failed to load: {error}</p>}

      {view === "map" && (
        <div className="mt-6">
          <ProjectsMapView
            filters={{
              territory,
              status,
              projectType,
              county,
              category,
              year,
              hasDocuments,
              documentType,
              query: debouncedQuery,
              newOnly,
            }}
          />
        </div>
      )}

      {view === "list" && (
      <ul className="mt-6 divide-y divide-[var(--color-border)] rounded-lg border border-[var(--color-border)] bg-white">
        {projects.map((project) => (
          <li key={project.id}>
            <Link
              href={`/projects/${project.id}/`}
              className="group block px-4 py-5 transition hover:bg-[var(--color-gray-100)] md:px-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    {project.score && (
                      <span className="rounded-full bg-[var(--color-amber)]/10 px-2 py-0.5 text-xs font-semibold text-[var(--color-amber)]">
                        🔥 {project.score.total}
                      </span>
                    )}
                    <h2 className="text-lg font-semibold tracking-tight group-hover:text-[var(--color-green)]">
                      {project.name}
                    </h2>
                    <StatusPill status={project.status} />
                    {project.has_documents && (
                      <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-gray-100)] px-2 py-0.5 text-xs font-medium text-[var(--color-gray-600)]">
                        📎 {project.document_count} doc{project.document_count === 1 ? "" : "s"}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-sm text-[var(--color-gray-600)]">
                    <span className="font-mono text-xs text-[var(--color-gray-400)]">{project.spx_id}</span>
                    {" · "}
                    {project.city}
                    {project.county ? `, ${project.county} County` : ""}, {stateName(project.state)}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold">{formatUsd(project.estimated_value_usd)}</p>
                  <p className="text-xs text-[var(--color-gray-600)]">{formatSf(project.square_footage)}</p>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <p className="text-xs text-[var(--color-gray-400)]">
                  {formatDate(project.opened_or_announced_date)}
                </p>
                {project.competitor_watch.slice(0, 3).map((cat) => (
                  <span
                    key={cat}
                    className="rounded-full bg-[var(--color-gray-100)] px-2 py-0.5 text-[10px] font-medium text-[var(--color-gray-600)]"
                  >
                    {cat}
                  </span>
                ))}
              </div>
            </Link>
          </li>
        ))}
        {!loading && projects.length === 0 && (
          <li className="px-4 py-16 text-center text-[var(--color-gray-600)]">No projects match.</li>
        )}
      </ul>
      )}

      {view === "list" && totalPages > 1 && (
        <div className="mt-6 flex items-center justify-between">
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            className="btn btn-outline disabled:opacity-40"
          >
            ← Previous
          </button>
          <span className="text-sm text-[var(--color-gray-600)]">Page {page} of {totalPages}</span>
          <button
            type="button"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="btn btn-outline disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
