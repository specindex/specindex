"use client";

import { useMemo, useState } from "react";
import type { CoverageEntry } from "@/lib/coverage";

type Props = {
  coverage: CoverageEntry[];
};

type SortKey = "project_count" | "state" | "county";

export function CoverageTable({ coverage }: Props) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<string>("all");
  const [coverageType, setCoverageType] = useState<string>("all");
  const [sortKey, setSortKey] = useState<SortKey>("project_count");

  const states = useMemo(
    () => Array.from(new Set(coverage.map((c) => c.state))).sort(),
    [coverage],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = coverage.filter((c) => {
      if (state !== "all" && c.state !== state) return false;
      if (coverageType !== "all" && c.coverage_type !== coverageType) return false;
      if (!q) return true;
      const blob = [c.state, c.county, ...c.sources].join(" ").toLowerCase();
      return blob.includes(q);
    });
    return [...rows].sort((a, b) => {
      if (sortKey === "project_count") return b.project_count - a.project_count;
      if (sortKey === "state") return a.state.localeCompare(b.state) || b.project_count - a.project_count;
      return a.county.localeCompare(b.county);
    });
  }, [coverage, query, state, coverageType, sortKey]);

  const totals = useMemo(() => {
    const deep = coverage.filter((c) => c.coverage_type === "deep").length;
    return { total: coverage.length, deep, thin: coverage.length - deep };
  }, [coverage]);

  return (
    <div>
      <div className="card p-4 md:p-5">
        <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
          Search state, county, or source
        </label>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="GA, Fulton, ArcGIS…"
          className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-4 py-3 text-base outline-none focus:border-[var(--color-green)] focus:ring-1 focus:ring-[var(--color-green)]"
        />
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <select
            value={state}
            onChange={(e) => setState(e.target.value)}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="all">All states</option>
            {states.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select
            value={coverageType}
            onChange={(e) => setCoverageType(e.target.value)}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="all">Deep + thin</option>
            <option value="deep">Deep only</option>
            <option value="thin">Thin only</option>
          </select>
          <select
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="project_count">Sort: most projects</option>
            <option value="state">Sort: state</option>
            <option value="county">Sort: county name</option>
          </select>
        </div>
        <p className="mt-4 text-sm text-[var(--color-gray-600)]">
          {filtered.length} of {coverage.length} counties · {totals.deep} deep, {totals.thin} thin overall
        </p>
      </div>

      <div className="mt-6 overflow-x-auto rounded-lg border border-[var(--color-border)] bg-white">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)] text-left text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
              <th className="px-4 py-3">State</th>
              <th className="px-4 py-3">County</th>
              <th className="px-4 py-3 text-right">Projects</th>
              <th className="px-4 py-3">Coverage</th>
              <th className="px-4 py-3">Sources</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {filtered.map((c) => (
              <tr key={`${c.state}-${c.county}`}>
                <td className="px-4 py-3 font-mono text-xs">{c.state}</td>
                <td className="px-4 py-3 font-medium">{c.county}</td>
                <td className="px-4 py-3 text-right tabular-nums">{c.project_count.toLocaleString()}</td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      c.coverage_type === "deep"
                        ? "bg-[var(--color-green)]/10 text-[var(--color-green)]"
                        : "bg-[var(--color-gray-100)] text-[var(--color-gray-600)]"
                    }`}
                  >
                    {c.coverage_type}
                  </span>
                </td>
                <td className="px-4 py-3 text-[var(--color-gray-600)]">{c.sources.join(", ")}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-16 text-center text-[var(--color-gray-600)]">
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
