"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Project } from "@/lib/types";
import { formatDate, formatSf, formatUsd, stateName, typeLabel } from "@/lib/format";
import { StatusPill } from "./StatusPill";

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";
const PAGE_SIZE = 50;

type Facets = {
  states: string[];
  counties: string[];
  project_types: string[];
  statuses: string[];
  categories: string[];
  years: number[];
};

type SortKey = "score" | "name" | "value" | "recency";

const EMPTY_FACETS: Facets = {
  states: [],
  counties: [],
  project_types: [],
  statuses: [],
  categories: [],
  years: [],
};

function buildQuery(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "" && v !== "all") usp.set(k, String(v));
  }
  return usp.toString();
}

export function ProjectsDashboard() {
  const [territory, setTerritory] = useState<string[]>([]);
  const [status, setStatus] = useState("all");
  const [projectType, setProjectType] = useState("all");
  const [county, setCounty] = useState("all");
  const [category, setCategory] = useState("all");
  const [year, setYear] = useState("all");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("score");
  const [offset, setOffset] = useState(0);

  const [facets, setFacets] = useState<Facets>(EMPTY_FACETS);
  const [projects, setProjects] = useState<Project[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Debounce free-text search so every keystroke doesn't fire a request.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  // Any filter change resets to page 1.
  const filterKey = JSON.stringify([territory, status, projectType, county, category, year, debouncedQuery, sort]);
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
      q: debouncedQuery,
      sort,
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
  }, [territory, status, projectType, county, category, year, debouncedQuery, sort, offset]);

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

  return (
    <div>
      <div className="card p-4 md:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <label className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
            Your territory
          </label>
          <span className="text-xs text-[var(--color-gray-600)]">{territoryLabel}</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {facets.states.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => toggleState(s)}
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
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
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
          <select value={category} onChange={(e) => setCategory(e.target.value)} className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm">
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
        </div>
        <p className="mt-4 text-sm text-[var(--color-gray-600)]">
          {loading ? "Loading…" : `${total.toLocaleString()} projects match · page ${page} of ${totalPages}`}
        </p>
      </div>

      {error && <p className="mt-4 text-sm text-red-600">Failed to load: {error}</p>}

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
              <p className="mt-2 text-xs text-[var(--color-gray-400)]">
                {formatDate(project.opened_or_announced_date)}
              </p>
            </Link>
          </li>
        ))}
        {!loading && projects.length === 0 && (
          <li className="px-4 py-16 text-center text-[var(--color-gray-600)]">No projects match.</li>
        )}
      </ul>

      {totalPages > 1 && (
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
