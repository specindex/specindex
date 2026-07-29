"use client";

import { useEffect, useMemo, useState } from "react";
import { StatusPill } from "./StatusPill";

type Doc = {
  title: string;
  url: string;
  doc_type: string;
  verify_kind?: string;
  confidence?: number;
  notes?: string;
  source_pass?: string;
};

type Project = {
  id: string;
  name: string;
  city: string;
  county: string;
  owner: string;
  project_type: string;
  status?: string;
  opened_or_announced_date?: string;
  estimated_value_usd?: number | null;
  origin?: string;
  flash_doc_count: number;
  sonnet_kept_count: number;
  verified_doc_count: number;
  html_page_count: number;
  downloaded_count: number;
  documents: Doc[];
};

type Payload = {
  generated_at?: string;
  pipeline?: string;
  sonnet_backend?: string;
  socrata?: {
    total_commercial?: number;
    months?: number;
    cutoff?: string;
    dataset?: string;
  };
  stats?: Record<string, number>;
  projects: Project[];
};

function formatUsd(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n) || n <= 0) return "n/a";
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${Math.round(n).toLocaleString()}`;
}

function typeLabel(t: string): string {
  return (t || "other").replaceAll("_", " ");
}

export function NjPipelineDashboard() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [origin, setOrigin] = useState("all");
  const [docsOnly, setDocsOnly] = useState(false);
  const [projectType, setProjectType] = useState("all");
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    fetch("/data/nj-flash-sonnet-pipeline.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((j: Payload) => setData(j))
      .catch((e) => setError(String(e)));
  }, []);

  const types = useMemo(() => {
    const s = new Set<string>();
    for (const p of data?.projects || []) {
      if (p.project_type) s.add(p.project_type);
    }
    return Array.from(s).sort();
  }, [data]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data?.projects || []).filter((p) => {
      if (docsOnly && p.verified_doc_count < 1) return false;
      if (origin !== "all" && !(p.origin || "").includes(origin)) return false;
      if (projectType !== "all" && p.project_type !== projectType) return false;
      if (!q) return true;
      const blob = `${p.name} ${p.city} ${p.county} ${p.owner} ${p.id}`.toLowerCase();
      return blob.includes(q);
    });
  }, [data, query, origin, docsOnly, projectType]);

  if (error) {
    return (
      <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
        Could not load pipeline data: {error}
      </p>
    );
  }

  if (!data) {
    return <p className="text-sm text-[var(--color-gray-600)]">Loading NJ pipeline…</p>;
  }

  const stats = data.stats || {};

  return (
    <div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-md border border-[var(--color-border)] bg-white px-4 py-3">
          <p className="text-xs uppercase tracking-wide text-[var(--color-gray-600)]">Socrata commercial</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            {(stats.socrata_total ?? data.socrata?.total_commercial ?? 0).toLocaleString()}
          </p>
        </div>
        <div className="rounded-md border border-[var(--color-border)] bg-white px-4 py-3">
          <p className="text-xs uppercase tracking-wide text-[var(--color-gray-600)]">Flash candidates</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{(stats.flash_raw ?? 0).toLocaleString()}</p>
        </div>
        <div className="rounded-md border border-[var(--color-border)] bg-white px-4 py-3">
          <p className="text-xs uppercase tracking-wide text-[var(--color-gray-600)]">Sonnet kept</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{(stats.sonnet_kept ?? 0).toLocaleString()}</p>
        </div>
        <div className="rounded-md border border-[var(--color-border)] bg-white px-4 py-3">
          <p className="text-xs uppercase tracking-wide text-[var(--color-gray-600)]">Verified files</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{(stats.verified_docs ?? 0).toLocaleString()}</p>
        </div>
      </div>

      <p className="mt-4 text-sm text-[var(--color-gray-600)]">
        Pipeline: {data.pipeline}. Sonnet via {data.sonnet_backend || "anthropic"}.
        {data.socrata?.cutoff ? ` Socrata cutoff ${data.socrata.cutoff}.` : null}
        {data.generated_at ? ` Generated ${data.generated_at.slice(0, 10)}.` : null}
      </p>

      <div className="mt-6 flex flex-wrap items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search city, owner, permit, project…"
          className="min-w-[220px] flex-1 rounded-md border border-[var(--color-border)] bg-white px-4 py-2.5 text-sm outline-none focus:border-[var(--color-amber)]"
        />
        <select
          value={origin}
          onChange={(e) => setOrigin(e.target.value)}
          className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2.5 text-sm"
        >
          <option value="all">All origins</option>
          <option value="socrata">Socrata</option>
          <option value="curated">Curated enrichment</option>
        </select>
        <select
          value={projectType}
          onChange={(e) => setProjectType(e.target.value)}
          className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2.5 text-sm"
        >
          <option value="all">All types</option>
          {types.map((t) => (
            <option key={t} value={t}>
              {typeLabel(t)}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => setDocsOnly((v) => !v)}
          className={`rounded-md border px-3 py-2.5 text-sm font-medium ${
            docsOnly
              ? "border-[var(--color-green)] bg-[var(--color-green)]/10 text-[var(--color-green)]"
              : "border-[var(--color-border)] text-[var(--color-gray-600)]"
          }`}
        >
          Verified docs only
        </button>
      </div>

      <p className="mt-3 text-sm text-[var(--color-gray-600)]">
        Showing {filtered.length.toLocaleString()} of {(data.projects || []).length.toLocaleString()} projects
      </p>

      <ul className="mt-4 divide-y divide-[var(--color-border)] rounded-md border border-[var(--color-border)] bg-white">
        {filtered.map((p) => {
          const open = expanded === p.id;
          return (
            <li key={p.id} className="px-4 py-4 md:px-5">
              <button
                type="button"
                className="flex w-full flex-col gap-2 text-left md:flex-row md:items-start md:justify-between"
                onClick={() => setExpanded(open ? null : p.id)}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-base font-semibold text-[var(--color-ink)]">{p.name}</h2>
                    {p.status ? <StatusPill status={p.status} /> : null}
                    <span className="rounded border border-[var(--color-border)] px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-[var(--color-gray-600)]">
                      {p.origin || "unknown"}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-[var(--color-gray-600)]">
                    {[p.city, p.county ? `${p.county} County` : "", typeLabel(p.project_type)]
                      .filter(Boolean)
                      .join(" · ")}
                    {p.owner ? ` · ${p.owner}` : ""}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-3 text-xs text-[var(--color-gray-600)] md:justify-end">
                  <span>{formatUsd(p.estimated_value_usd)}</span>
                  <span>Flash {p.flash_doc_count}</span>
                  <span>Sonnet {p.sonnet_kept_count}</span>
                  <span className="font-semibold text-[var(--color-green)]">
                    Verified {p.verified_doc_count}
                  </span>
                  {p.downloaded_count > 0 ? <span>Downloaded {p.downloaded_count}</span> : null}
                </div>
              </button>
              {open && (
                <div className="mt-3 border-t border-[var(--color-border)] pt-3">
                  <p className="text-xs text-[var(--color-gray-600)]">{p.id}</p>
                  {p.documents.length === 0 ? (
                    <p className="mt-2 text-sm text-[var(--color-gray-600)]">
                      No verified documents from this pipeline run.
                    </p>
                  ) : (
                    <ul className="mt-2 space-y-2">
                      {p.documents.map((d, i) => (
                        <li key={`${d.url}-${i}`} className="text-sm">
                          <a
                            href={d.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-[var(--color-green)] hover:underline"
                          >
                            {d.title || d.url}
                          </a>
                          <span className="ml-2 text-xs text-[var(--color-gray-600)]">
                            {d.doc_type || "doc"} · {d.verify_kind || "unknown"}
                            {d.source_pass ? ` · ${d.source_pass}` : ""}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
