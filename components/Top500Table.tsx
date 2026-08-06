"use client";

import { useMemo, useState } from "react";
import type { Top500Coverage } from "@/lib/coverage";

type Props = {
  data: Top500Coverage;
};

type SortKey = "rank" | "projects" | "documents" | "state" | "gap";

const STATUS_LABEL: Record<string, string> = {
  covered: "covered",
  "projects-only": "projects only",
  none: "no data",
};

export function Top500Table({ data }: Props) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState("all");
  const [status, setStatus] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("rank");

  const states = useMemo(
    () => Array.from(new Set(data.counties.map((c) => c.state))).sort(),
    [data.counties],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = data.counties.filter((c) => {
      if (state !== "all" && c.state !== state) return false;
      if (status !== "all" && c.status !== status) return false;
      if (!q) return true;
      return `${c.county} ${c.state}`.toLowerCase().includes(q);
    });
    return [...rows].sort((a, b) => {
      switch (sortKey) {
        case "projects":
          return b.projects_in_window - a.projects_in_window;
        case "documents":
          return b.documents - a.documents;
        case "state":
          return a.state.localeCompare(b.state) || a.rank - b.rank;
        // "Biggest gap" is the whole point of this tab: the largest counties
        // where we hold the least. Ranking by population among the empties
        // surfaces those first instead of burying them at rank 400+.
        case "gap":
          if (a.projects_in_window === 0 && b.projects_in_window !== 0) return -1;
          if (b.projects_in_window === 0 && a.projects_in_window !== 0) return 1;
          return a.rank - b.rank;
        default:
          return a.rank - b.rank;
      }
    });
  }, [data.counties, query, state, status, sortKey]);

  const s = data.summary;

  return (
    <div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Covered", value: s.covered, hint: "projects + documents" },
          { label: "Projects only", value: s.projects_only, hint: "no documents yet" },
          { label: "No data", value: s.none, hint: "nothing in window" },
          { label: "Documents", value: s.total_documents, hint: "across top 500" },
        ].map((k) => (
          <div key={k.label} className="card p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
              {k.label}
            </p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">
              {k.value.toLocaleString()}
            </p>
            <p className="mt-0.5 text-xs text-[var(--color-gray-600)]">{k.hint}</p>
          </div>
        ))}
      </div>

      <div className="card mt-6 p-4 md:p-5">
        <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
          Search county or state
        </label>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Harris, CA, Cook…"
          className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-4 py-3 text-base outline-none focus:border-[var(--color-green)] focus:ring-1 focus:ring-[var(--color-green)]"
        />
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <select
            value={state}
            onChange={(e) => setState(e.target.value)}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="all">All states</option>
            {states.map((st) => (
              <option key={st} value={st}>
                {st}
              </option>
            ))}
          </select>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="all">All statuses</option>
            <option value="covered">Covered</option>
            <option value="projects-only">Projects only</option>
            <option value="none">No data</option>
          </select>
          <select
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="rank">Sort: population rank</option>
            <option value="gap">Sort: biggest gap</option>
            <option value="projects">Sort: most projects</option>
            <option value="documents">Sort: most documents</option>
            <option value="state">Sort: state</option>
          </select>
        </div>
        <p className="mt-4 text-sm text-[var(--color-gray-600)]">
          {filtered.length} of {s.total} counties · {s.total_projects_in_window.toLocaleString()}{" "}
          projects since {data.window_start}
        </p>
      </div>

      <div className="mt-6 overflow-x-auto rounded-lg border border-[var(--color-border)] bg-white">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)] text-left text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
              <th className="px-4 py-3 text-right">#</th>
              <th className="px-4 py-3">County</th>
              <th className="px-4 py-3">State</th>
              <th className="px-4 py-3 text-right">Population</th>
              <th className="px-4 py-3 text-right">Projects</th>
              <th className="px-4 py-3 text-right">Documents</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {filtered.map((c) => (
              <tr key={`${c.state}-${c.county}`}>
                <td className="px-4 py-3 text-right tabular-nums text-[var(--color-gray-400)]">
                  {c.rank}
                </td>
                <td className="px-4 py-3 font-medium">{c.county}</td>
                <td className="px-4 py-3 font-mono text-xs">{c.state}</td>
                <td className="px-4 py-3 text-right tabular-nums text-[var(--color-gray-600)]">
                  {c.population.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {c.projects_in_window.toLocaleString()}
                </td>
                <td
                  className={`px-4 py-3 text-right tabular-nums ${
                    c.documents === 0 ? "text-[var(--color-gray-400)]" : ""
                  }`}
                >
                  {c.documents.toLocaleString()}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      c.status === "covered"
                        ? "bg-[var(--color-green)]/10 text-[var(--color-green)]"
                        : c.status === "projects-only"
                          ? "bg-[var(--color-amber)]/10 text-[var(--color-amber)]"
                          : "bg-[var(--color-gray-100)] text-[var(--color-gray-600)]"
                    }`}
                  >
                    {STATUS_LABEL[c.status]}
                  </span>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-16 text-center text-[var(--color-gray-600)]">
                  No counties match.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
