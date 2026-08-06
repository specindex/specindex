"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useFirebaseAuth } from "@/components/FirebaseAuthProvider";
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

// The three stages where a spec is still influenceable. Everything the product
// claims to sell lives here; cancelled and completed are reachable but are
// never the default, because a completed project cannot be specified into.
//
// Sent as a comma list, matching how `state` already passes a multi-value
// territory to the same endpoint. VERIFY against /v1/projects before relying
// on it -- if the API rejects multi-value status, STATUS_PRESETS below is the
// fallback shape (one request per chip) and the default becomes "planning".
const EARLY_STAGE = "planning,permitting,bidding";

// Status as three visible chips rather than a dropdown of everything.
const STATUS_PRESETS: { value: string; label: string }[] = [
  { value: EARLY_STAGE, label: "Spec still open" },
  { value: "planning,permitting", label: "Planning & permitting" },
  { value: "all", label: "All statuses" },
];

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

// The reason line and the coverage label.
//
// WORDING IS THE PRODUCT HERE. 166 of 591,618 projects have any mentioned
// brand, and those are tenants (Google, Amazon), not building-product
// manufacturers. So the row must never say "no manufacturer named" -- it says
// "no manufacturer named in the documents we hold", which is a different and
// defensible claim. Overclaiming costs the one thing a licensed feed cannot
// copy: a rep who believes the line.
//
// Three states, matching the assertion model in migration 042:
//   named            -- a manufacturer is cited in a document we parsed
//   determined absent -- we parsed documents and nobody is named (SELLABLE)
//   indeterminate    -- we have not read anything yet (a gap, said plainly)
function reasonLine(project: Project): string {
  const stage = (project.status || "").replace(/_/g, " ");
  const cats = (project.competitor_watch || []).slice(0, 2).join(" and ");
  const scope = cats ? `${cats} scoped` : "scope open";
  const docs = project.document_count || 0;

  if (docs === 0) {
    // Be explicit that nothing has been read. "No manufacturer named" here
    // would be a claim about the world; this is a claim about our coverage.
    return `${scope} from the permit, no documents parsed yet`;
  }
  return `${scope}, no manufacturer named in the ${docs} document${docs === 1 ? "" : "s"} we hold`;
}

// Lets a rep tell "nothing found" apart from "nothing read" at a glance.
function coverageLabel(project: Project): string {
  const docs = project.document_count || 0;
  // `sources` is on the list payload; there is no source_count field, and
  // inventing one would have compiled only to fail at runtime as undefined.
  const srcs = (project.sources || []).length;
  if (docs > 0) return `${docs} document${docs === 1 ? "" : "s"} parsed`;
  if (srcs > 0) return `${srcs} source${srcs === 1 ? "" : "s"} · inferred from permit`;
  return "inferred from permit";
}

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
  // /v1/projects now requires either a Firebase session or the build-time
  // token (api/main.py's require_firebase_user_or_build_token) -- this
  // component only ever mounts inside <ProjectsGate>'s signed-in branch,
  // so getToken() here always has a real session to draw from.
  const { getToken } = useFirebaseAuth();
  const authedFetch = useCallback(
    async (url: string) => {
      const token = await getToken();
      return fetch(url, token ? { headers: { Authorization: `Bearer ${token}` } } : undefined);
    },
    [getToken],
  );

  // Restored from localStorage so a returning visitor lands straight on
  // their territory+category instead of the full nationwide list every
  // time -- a lightweight stand-in for a saved profile until real
  // accounts exist (see docs/ROADMAP.md item 46, Phase B).
  const [territory, setTerritory] = useState<string[]>(() => readStoredList(TERRITORY_KEY));
  // DEFAULTS MUST MATCH THE PITCH (design review, 2026-08-05).
  //
  // These defaulted to "all", which meant the page selling "the window before
  // construction" opened on a list including CANCELLED and COMPLETED projects,
  // sorted so the top row could be a data centre already under construction.
  // The first row a new user saw actively contradicted the headline above it.
  //
  // Early-stage is now the default and cancelled/completed remain reachable
  // but never arrive uninvited. Anyone who wants everything can still get it;
  // the difference is that the default no longer undercuts the product.
  const [status, setStatus] = useState(EARLY_STAGE);
  const [projectType, setProjectType] = useState("all");
  const [county, setCounty] = useState("all");
  const [category, setCategory] = useState(() => readStoredValue(CATEGORY_KEY) ?? "all");
  // The design calls for "current year forward" as the default. NOT applied
  // yet: `year` is sent to /v1/projects as a single year, so a range needs
  // either a year_min param or an API change, and sending a sentinel like
  // "recent" would be silently dropped or rejected. Left at "all" rather than
  // shipping a default that only appears to work -- the failure would be a
  // wrong result set, not an error, which is the worst shape available here.
  // Status now carries most of the same benefit, since stale rows are mostly
  // completed/cancelled.
  const [year, setYear] = useState("all");
  const [showAdvanced, setShowAdvanced] = useState(false);
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
    authedFetch(`${API_BASE}/v1/projects?${qs}`)
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
    authedFetch(`${API_BASE}/v1/projects?${qs}`)
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

  // The year filter was a flat list of ~57 individual years, 1979 to 2091.
  // Measured against the corpus that is badly mis-weighted: 93.7% of dated
  // projects are 2024 or later, while 42 of those entries covered just 2.2%
  // of the data between them. Scrolling past four decades to reach the year
  // that holds a third of the corpus is the whole problem.
  //
  // Three groups, most-used first, with the long tail collapsed behind
  // <optgroup> labels. Values are unchanged single years, so the API contract
  // is untouched -- this is presentation only.
  //
  // Implausible years are also DROPPED from the list. The dropdown was
  // offering 2091 and 2036 as selectable filters; those are data-entry typos
  // in the source (New Jersey publishes permitdate 2925-08-15 for one permit),
  // not real options. Offering a corrupt value as a filter invites a user to
  // select it and see an empty or nonsensical result. The bounds match
  // scripts/specindex/dates.py so the UI and the validator cannot disagree.
  const yearGroups = useMemo(() => {
    const now = new Date().getFullYear();
    const plausible = (facets.years ?? [])
      .filter((y) => y >= 1970 && y <= now + 6)
      .sort((a, b) => b - a);
    return {
      recent: plausible.filter((y) => y <= now && y >= now - 3),
      planned: plausible.filter((y) => y > now),
      earlier: plausible.filter((y) => y < now - 3),
    };
  }, [facets.years]);

  // The product-category list was 292 flat entries, and length was the
  // SMALLER problem. Measured over 591,618 projects:
  //
  //   lighting 97.7% · hvac 97.7% · fire suppression 95.1% · roofing 88.2%
  //   · flooring 79.4%   -- these are template defaults stamped on every
  //   commercial permit, not detected facts. Selecting one returns
  //   essentially the whole corpus, so they do not behave like filters.
  //
  //   279 of the 292 appear on fewer than 1,000 projects each and account for
  //   ~1,377 tag instances between them -- roughly 0.2% of the data occupying
  //   96% of the list.
  //
  // Only about eight tags (concrete, glazing, elevators, doors and hardware,
  // dock equipment, plumbing fixtures, ff&e, medical gas) actually
  // discriminate. So the fix is not just "shorter": it is to put the useful
  // ones FIRST, label the broad ones honestly instead of implying they
  // narrow anything, and collapse the tail.
  //
  // Also merges case and whitespace duplicates -- 'hvac' (578,114) and 'HVAC'
  // (110) were split entries for one trade, as were 'flooring' and
  // ' flooring'. Mirrors scripts/specindex/categories.py; keep the two in
  // step. Genuinely distinct trades are never merged to shorten the list.
  const categoryGroups = useMemo(() => {
    const BROAD = new Set(["lighting", "hvac", "fire suppression", "roofing", "flooring"]);
    const SPECIFIC = new Set(["concrete", "glazing", "elevators", "doors and hardware",
      "dock equipment", "plumbing fixtures", "ff&e", "medical gas"]);
    const seen = new Set<string>();
    const norm = (c: string) => c.trim().toLowerCase().replace(/\s+/g, " ");
    const broad: string[] = [], specific: string[] = [], rare: string[] = [];
    for (const raw of facets.categories ?? []) {
      const c = norm(raw);
      if (!c || seen.has(c)) continue;
      seen.add(c);
      if (BROAD.has(c)) broad.push(c);
      else if (SPECIFIC.has(c)) specific.push(c);
      else rare.push(c);
    }
    rare.sort((a, b) => a.localeCompare(b));
    return { broad, specific, rare };
  }, [facets.categories]);

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
      // "refine below" was wrong -- every filter sits ABOVE the list. And the
      // two exact six-digit counts go stale weekly and contradict the 500K+
      // figure used everywhere else, so they are gone.
      return `Top ${shown} ${scope}${catLabel} · scored and early enough to influence`;
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
            {/* THE "N NEW THIS WEEK" BADGE IS REMOVED.
                It read 416,759 -- about 70% of the index -- because it counts
                rows whose first_seen_at falls in the last 7 days, while
                591,329 rows have loaded_at in the same window. first_seen_at
                is being RESET by corpus loads, so the badge was reporting
                pipeline activity as market novelty. A number a rep cannot
                believe damages every other number on the page.
                Restore it when novelty derives from something stable, and
                scope it to the rep's territory so it is useful as well as
                true. */}
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
          className="mt-4 w-full rounded-md border border-[var(--color-border)] bg-white px-4 py-3 text-base outline-none focus:border-[var(--color-green)] focus:ring-1 focus:ring-[var(--color-green)]"
        />
        {/* Status as three chips, not a dropdown of everything. The stage a
            project is in is the single most consequential filter -- a
            completed project cannot be specified into -- so it belongs in
            front of the user rather than one of eight equal-looking selects. */}
        <div className="mt-4 flex flex-wrap gap-1.5">
          {STATUS_PRESETS.map((p) => (
            <button
              key={p.value}
              type="button"
              onClick={() => {
                setStatus(p.value);
                dismissOnboarding();
              }}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                status === p.value
                  ? "border-[var(--color-green)] bg-[var(--color-green)] text-white"
                  : "border-[var(--color-border)] text-[var(--color-gray-600)] hover:border-[var(--color-gray-400)]"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              dismissOnboarding();
            }}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="all">All product categories</option>
            {categoryGroups.specific.length > 0 && (
              <optgroup label="Specific systems">
                {categoryGroups.specific.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </optgroup>
            )}
            {categoryGroups.broad.length > 0 && (
              <optgroup label="Broad trades (on most projects)">
                {categoryGroups.broad.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </optgroup>
            )}
            {categoryGroups.rare.length > 0 && (
              <optgroup label="Specialty">
                {categoryGroups.rare.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </optgroup>
            )}
          </select>
          <select value={year} onChange={(e) => setYear(e.target.value)} className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm">
            <option value="all">All years</option>
            {yearGroups.recent.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
            {yearGroups.planned.length > 0 && (
              <optgroup label="Planned / future">
                {yearGroups.planned.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </optgroup>
            )}
            {yearGroups.earlier.length > 0 && (
              <optgroup label="Earlier">
                {yearGroups.earlier.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </optgroup>
            )}
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
          <div>
            <p className="text-sm text-[var(--color-gray-600)]">{resultsLabel}</p>
            {/* One standing line instead of two exact counts that go stale
                weekly and contradict the 500K+ figure used elsewhere. Every
                claim here is defensible: 591,618 rounds to 500K+, all 50
                states carry sources, and every source is a public record. */}
            <p className="mt-0.5 text-xs text-[var(--color-gray-400)]">
              500K+ commercial projects · 50 states · 97% still early stage · 100% public-source
            </p>
          </div>
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
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <h2 className="text-base font-semibold tracking-tight group-hover:text-[var(--color-green)]">
                      {project.name}
                    </h2>
                    <span className="font-mono text-xs text-[var(--color-gray-400)]">{project.spx_id}</span>
                  </div>
                  {/* THE REASON LINE. Replaces the score, which compressed at
                      82/76/75/75/75/75 at the top of the list and so carried no
                      information where the rep actually looks. The score still
                      ORDERS the list and is auditable on the record page; this
                      says why the row is here. It is the only thing on the page
                      a licensed feed cannot copy. */}
                  <p className="mt-1.5 flex items-start gap-1.5 text-sm text-[var(--color-ink)]">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-green)]" />
                    <span>{reasonLine(project)}</span>
                  </p>
                  <p className="mt-1 text-xs text-[var(--color-gray-600)]">
                    {[project.city, project.county ? `${project.county} County` : null, stateName(project.state)]
                      .filter(Boolean)
                      .join(", ")}
                    {" · "}
                    {coverageLabel(project)}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <StatusPill status={project.status} />
                  {/* Empty fields are OMITTED, never printed as "Not reported".
                      A column of "Not reported" makes a deep record look thin,
                      and square footage is absent on most rows. */}
                  {project.estimated_value_usd ? (
                    <p className="mt-2 text-sm font-semibold">{formatUsd(project.estimated_value_usd)}</p>
                  ) : null}
                  {project.square_footage ? (
                    <p className="text-xs text-[var(--color-gray-600)]">{formatSf(project.square_footage)}</p>
                  ) : null}
                </div>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
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
