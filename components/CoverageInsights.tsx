"use client";

import Link from "next/link";
import { Fragment, useMemo, useState } from "react";
import type { CoverageInsights as CoverageInsightsData } from "@/lib/coverage";
import { formatDate, formatUsd } from "@/lib/format";

type Props = {
  insights: CoverageInsightsData;
};

type SortKey = "coverage_pct" | "counties_uncovered" | "total_projects" | "state";

export function CoverageInsights({ insights }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("counties_uncovered");
  const [expanded, setExpanded] = useState<string | null>(null);

  const sorted = useMemo(() => {
    return [...insights.state_summary].sort((a, b) => {
      if (sortKey === "state") return a.state.localeCompare(b.state);
      if (sortKey === "counties_uncovered")
        return (b.counties_uncovered ?? 0) - (a.counties_uncovered ?? 0);
      if (sortKey === "total_projects") return b.total_projects - a.total_projects;
      return (b.coverage_pct ?? 0) - (a.coverage_pct ?? 0);
    });
  }, [insights.state_summary, sortKey]);

  const totals = useMemo(() => {
    const totalCounties = insights.state_summary.reduce(
      (sum, s) => sum + (s.total_us_counties ?? 0),
      0,
    );
    const covered = insights.state_summary.reduce((sum, s) => sum + s.counties_covered, 0);
    const deep = insights.state_summary.reduce((sum, s) => sum + s.deep, 0);
    return { totalCounties, covered, deep, uncovered: totalCounties - covered };
  }, [insights.state_summary]);

  const countiesForState = useMemo(() => {
    if (!expanded) return [];
    return Object.keys(insights.top_projects_by_county)
      .filter((key) => key.startsWith(`${expanded}|`))
      .map((key) => key.slice(expanded.length + 1))
      .sort();
  }, [expanded, insights.top_projects_by_county]);

  return (
    <div>
      <div className="card p-4 md:p-5">
        <p className="text-sm text-[var(--color-gray-600)]">
          <span className="font-semibold text-[var(--color-ink)]">
            {totals.covered.toLocaleString()}
          </span>{" "}
          of{" "}
          <span className="font-semibold text-[var(--color-ink)]">
            {totals.totalCounties.toLocaleString()}
          </span>{" "}
          US counties have at least one project ({totals.deep} deep,{" "}
          {(totals.covered - totals.deep).toLocaleString()} thin) ·{" "}
          <span className="font-semibold text-[var(--color-ink)]">
            {totals.uncovered.toLocaleString()}
          </span>{" "}
          counties have zero projects. Goal: close that gap, one verified source at a time.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setSortKey("counties_uncovered")}
            className={`rounded-md border px-3 py-1.5 text-xs font-medium ${sortKey === "counties_uncovered" ? "border-[var(--color-amber)] bg-[var(--color-amber)]/10" : "border-[var(--color-border)]"}`}
          >
            Most room to grow
          </button>
          <button
            type="button"
            onClick={() => setSortKey("coverage_pct")}
            className={`rounded-md border px-3 py-1.5 text-xs font-medium ${sortKey === "coverage_pct" ? "border-[var(--color-amber)] bg-[var(--color-amber)]/10" : "border-[var(--color-border)]"}`}
          >
            Highest coverage %
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
              <th className="px-4 py-3 text-right">Counties covered</th>
              <th className="px-4 py-3 text-right">Uncovered</th>
              <th className="px-4 py-3 text-right">Coverage %</th>
              <th className="px-4 py-3 text-right">Deep</th>
              <th className="px-4 py-3 text-right">Thin</th>
              <th className="px-4 py-3 text-right">Projects</th>
              <th className="px-4 py-3 text-right">Since last run</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {sorted.map((s) => (
              <Fragment key={s.state}>
                <tr>
                  <td className="px-4 py-3 font-mono text-xs font-medium">{s.state}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {s.counties_covered}
                    {s.total_us_counties ? ` / ${s.total_us_counties}` : ""}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-[var(--color-gray-600)]">
                    {s.counties_uncovered ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {s.coverage_pct !== null ? `${s.coverage_pct}%` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{s.deep}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{s.thin}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {s.total_projects.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {s.net_delta === null ? (
                      <span className="text-[var(--color-gray-400)]">—</span>
                    ) : s.net_delta > 0 ? (
                      <span className="text-[var(--color-green)]">+{s.net_delta}</span>
                    ) : s.net_delta < 0 ? (
                      <span className="text-red-600">{s.net_delta}</span>
                    ) : (
                      <span className="text-[var(--color-gray-400)]">0</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => setExpanded(expanded === s.state ? null : s.state)}
                      className="text-xs font-medium text-[var(--color-green)] hover:underline"
                    >
                      {expanded === s.state ? "Hide" : "Top projects"}
                    </button>
                  </td>
                </tr>
                {expanded === s.state && (
                  <tr>
                    <td colSpan={9} className="bg-[var(--color-gray-100)] px-4 py-4">
                      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        {countiesForState.map((county) => {
                          const key = `${s.state}|${county}`;
                          const projects = insights.top_projects_by_county[key] ?? [];
                          return (
                            <div key={key} className="rounded-md border border-[var(--color-border)] bg-white p-3">
                              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
                                {county} County
                              </p>
                              <ul className="mt-2 space-y-2">
                                {projects.map((p) => (
                                  <li key={p.id} className="text-xs">
                                    <Link
                                      href={`/projects/${p.id}/`}
                                      className="font-medium text-[var(--color-ink)] hover:text-[var(--color-green)]"
                                    >
                                      {p.name}
                                    </Link>
                                    <p className="mt-0.5 text-[var(--color-gray-600)]">
                                      {formatUsd(p.estimated_value_usd)}
                                      {p.opened_or_announced_date
                                        ? ` · ${formatDate(p.opened_or_announced_date)}`
                                        : ""}{" "}
                                      · {p.status.replaceAll("_", " ")}
                                    </p>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          );
                        })}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
