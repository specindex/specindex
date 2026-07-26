"use client";

import { useMemo, useState } from "react";
import type { StateQuality as StateQualityRow } from "@/lib/coverage";

type Props = {
  quality: StateQualityRow[];
};

type SortKey = "freshness_days" | "completeness" | "total_projects" | "state";

function completeness(r: StateQualityRow): number {
  return (r.pct_has_city + r.pct_has_value + r.pct_has_contractor + r.pct_has_date) / 4;
}

export function StateQuality({ quality }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("freshness_days");

  const sorted = useMemo(() => {
    return [...quality].sort((a, b) => {
      if (sortKey === "state") return a.state.localeCompare(b.state);
      if (sortKey === "total_projects") return b.total_projects - a.total_projects;
      if (sortKey === "completeness") return completeness(b) - completeness(a);
      return (b.freshness_days ?? 0) - (a.freshness_days ?? 0);
    });
  }, [quality, sortKey]);

  return (
    <div>
      <div className="card p-4 md:p-5">
        <p className="text-sm text-[var(--color-gray-600)]">
          Field completeness (city, value, contractor, date) and freshness (days since the
          newest project) per state. Low completeness usually means a wired source has a
          sparse schema; a large freshness gap usually means a pull script hasn&rsquo;t run
          recently or the source stopped updating.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setSortKey("freshness_days")}
            className={`rounded-md border px-3 py-1.5 text-xs font-medium ${sortKey === "freshness_days" ? "border-[var(--color-amber)] bg-[var(--color-amber)]/10" : "border-[var(--color-border)]"}`}
          >
            Stalest first
          </button>
          <button
            type="button"
            onClick={() => setSortKey("completeness")}
            className={`rounded-md border px-3 py-1.5 text-xs font-medium ${sortKey === "completeness" ? "border-[var(--color-amber)] bg-[var(--color-amber)]/10" : "border-[var(--color-border)]"}`}
          >
            Lowest completeness first
          </button>
          <button
            type="button"
            onClick={() => setSortKey("total_projects")}
            className={`rounded-md border px-3 py-1.5 text-xs font-medium ${sortKey === "total_projects" ? "border-[var(--color-amber)] bg-[var(--color-amber)]/10" : "border-[var(--color-border)]"}`}
          >
            Most projects
          </button>
          <button
            type="button"
            onClick={() => setSortKey("state")}
            className={`rounded-md border px-3 py-1.5 text-xs font-medium ${sortKey === "state" ? "border-[var(--color-amber)] bg-[var(--color-amber)]/10" : "border-[var(--color-border)]"}`}
          >
            State A-Z
          </button>
        </div>
      </div>

      <div className="mt-6 overflow-x-auto rounded-lg border border-[var(--color-border)] bg-white">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)] text-left text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
              <th className="px-4 py-3">State</th>
              <th className="px-4 py-3 text-right">Projects</th>
              <th className="px-4 py-3 text-right">Has city</th>
              <th className="px-4 py-3 text-right">Has value</th>
              <th className="px-4 py-3 text-right">Has contractor</th>
              <th className="px-4 py-3 text-right">Has date</th>
              <th className="px-4 py-3 text-right">Freshness</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {sorted.map((r) => (
              <tr key={r.state}>
                <td className="px-4 py-3 font-mono text-xs font-medium">{r.state}</td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {r.total_projects.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{r.pct_has_city.toFixed(0)}%</td>
                <td className="px-4 py-3 text-right tabular-nums">{r.pct_has_value.toFixed(0)}%</td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {r.pct_has_contractor.toFixed(0)}%
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{r.pct_has_date.toFixed(0)}%</td>
                <td className="px-4 py-3 text-right tabular-nums text-[var(--color-gray-600)]">
                  {r.freshness_days !== null ? `${r.freshness_days}d ago` : "—"}
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-16 text-center text-[var(--color-gray-600)]">
                  No quality data yet — run scripts/compute-state-quality.py.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
