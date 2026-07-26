"use client";

import { Fragment, useEffect, useState } from "react";

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

type PipelineRun = {
  id: number;
  workflow: string;
  run_url: string | null;
  started_at: string | null;
  projects_before: number | null;
  projects_after: number | null;
  step_outcomes: Record<string, string>;
  top_movers: string | null;
  overall_status: "success" | "partial_failure" | "failure";
};

type DbHealth = {
  min_conn: number;
  max_conn: number;
  in_use: number;
  idle: number;
};

type StateSummary = {
  state: string;
  counties_covered: number;
  counties_uncovered: number | null;
  total_projects: number;
};

type StateQuality = {
  state: string;
  total_projects: number;
  pct_has_city: number;
  pct_has_value: number;
  pct_has_contractor: number;
  pct_has_date: number;
  freshness_days: number | null;
};

function StatusBadge({ status }: { status: PipelineRun["overall_status"] }) {
  const cls =
    status === "success"
      ? "bg-[var(--color-green)]/10 text-[var(--color-green)]"
      : status === "partial_failure"
        ? "bg-[var(--color-amber)]/10 text-[var(--color-amber)]"
        : "bg-red-100 text-red-700";
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status.replace("_", " ")}
    </span>
  );
}

export function OpsDashboard() {
  const [apiUp, setApiUp] = useState<boolean | null>(null);
  const [dbHealth, setDbHealth] = useState<DbHealth | null>(null);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [runCounts, setRunCounts] = useState<Record<string, number>>({});
  const [states, setStates] = useState<StateSummary[]>([]);
  const [quality, setQuality] = useState<StateQuality[]>([]);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [healthRes, dbRes, runsRes, insightsRes, qualityRes] = await Promise.all([
          fetch(`${API_BASE}/health`).then((r) => r.ok).catch(() => false),
          fetch(`${API_BASE}/v1/ops/db-health`).then((r) => r.json()),
          fetch(`${API_BASE}/v1/ops/pipeline-runs?limit=20`).then((r) => r.json()),
          fetch(`${API_BASE}/v1/coverage/insights`).then((r) => r.json()),
          fetch(`${API_BASE}/v1/quality`).then((r) => r.json()),
        ]);
        if (cancelled) return;
        setApiUp(healthRes);
        setDbHealth(dbRes);
        setRuns(runsRes.runs ?? []);
        setRunCounts(runsRes.run_counts ?? {});
        setStates(insightsRes.state_summary ?? []);
        setQuality(qualityRes.quality ?? []);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const totalProjects = states.reduce((sum, s) => sum + s.total_projects, 0);
  const totalCovered = states.reduce((sum, s) => sum + s.counties_covered, 0);
  const stalestStates = [...quality].sort(
    (a, b) => (b.freshness_days ?? -Infinity) - (a.freshness_days ?? -Infinity),
  ).slice(0, 5);

  if (loading) {
    return <p className="text-sm text-[var(--color-gray-600)]">Loading live status…</p>;
  }
  if (error) {
    return <p className="text-sm text-red-600">Failed to load ops data: {error}</p>;
  }

  return (
    <div className="space-y-8">
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
            API status
          </p>
          <p className="mt-1 text-lg font-semibold">
            {apiUp ? (
              <span className="text-[var(--color-green)]">● Up</span>
            ) : (
              <span className="text-red-600">● Down</span>
            )}
          </p>
          <p className="mt-1 text-xs text-[var(--color-gray-600)]">Live ping to /health</p>
        </div>
        <div className="card p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
            DB connection pool
          </p>
          <p className="mt-1 text-lg font-semibold">
            {dbHealth ? `${dbHealth.in_use} in use / ${dbHealth.idle} idle` : "—"}
          </p>
          <p className="mt-1 text-xs text-[var(--color-gray-600)]">
            Max {dbHealth?.max_conn ?? "—"} (db-f1-micro, 25 total server connections)
          </p>
        </div>
        <div className="card p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
            Total projects / counties covered
          </p>
          <p className="mt-1 text-lg font-semibold">
            {totalProjects.toLocaleString()} / {totalCovered}
          </p>
          <p className="mt-1 text-xs text-[var(--color-gray-600)]">
            Across {states.length} states with any coverage
          </p>
        </div>
        <div className="card p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
            Agent/cron runs (lifetime)
          </p>
          <p className="mt-1 text-lg font-semibold">
            {Object.values(runCounts).reduce((sum, n) => sum + n, 0)}
          </p>
          <p className="mt-1 text-xs text-[var(--color-gray-600)]">
            {Object.entries(runCounts)
              .map(([w, n]) => `${w}: ${n}`)
              .join(" · ") || "none logged yet"}
          </p>
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold">Pipeline runs</h2>
        <p className="mt-1 text-sm text-[var(--color-gray-600)]">
          Every scheduled + on-demand run of{" "}
          <code>pull-national.yml</code> / <code>pull-state.yml</code>, most recent first.
        </p>
        <div className="mt-4 overflow-x-auto rounded-lg border border-[var(--color-border)] bg-white">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-left text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
                <th className="px-4 py-3">Started</th>
                <th className="px-4 py-3">Workflow</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Projects</th>
                <th className="px-4 py-3">Top movers</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {runs.map((r) => (
                <Fragment key={r.id}>
                  <tr>
                    <td className="px-4 py-3 text-xs text-[var(--color-gray-600)]">
                      {r.started_at ? new Date(r.started_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">{r.workflow}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={r.overall_status} />
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {r.projects_before ?? "—"} → {r.projects_after ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--color-gray-600)]">
                      {r.top_movers || "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => setExpanded(expanded === r.id ? null : r.id)}
                        className="text-xs font-medium text-[var(--color-green)] hover:underline"
                      >
                        {expanded === r.id ? "Hide" : "Steps"}
                      </button>
                    </td>
                  </tr>
                  {expanded === r.id && (
                    <tr>
                      <td colSpan={6} className="bg-[var(--color-gray-100)] px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(r.step_outcomes).map(([step, outcome]) => (
                            <span
                              key={step}
                              className={`rounded-md px-2 py-1 text-xs font-mono ${
                                outcome === "success"
                                  ? "bg-[var(--color-green)]/10 text-[var(--color-green)]"
                                  : "bg-red-100 text-red-700"
                              }`}
                            >
                              {step}: {outcome}
                            </span>
                          ))}
                        </div>
                        {r.run_url && (
                          <a
                            href={r.run_url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-2 inline-block text-xs text-[var(--color-green)] hover:underline"
                          >
                            View run on GitHub →
                          </a>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-[var(--color-gray-600)]">
                    No pipeline runs logged yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold">Data staleness watchlist</h2>
        <p className="mt-1 text-sm text-[var(--color-gray-600)]">
          States with the largest gap since their newest project record — a proxy for a
          source that&apos;s stopped updating.
        </p>
        <div className="mt-4 overflow-x-auto rounded-lg border border-[var(--color-border)] bg-white">
          <table className="w-full min-w-[480px] text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-left text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
                <th className="px-4 py-3">State</th>
                <th className="px-4 py-3 text-right">Projects</th>
                <th className="px-4 py-3 text-right">Freshness</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {stalestStates.map((s) => (
                <tr key={s.state}>
                  <td className="px-4 py-3 font-mono text-xs">{s.state}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {s.total_projects.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-[var(--color-gray-600)]">
                    {s.freshness_days !== null ? `${s.freshness_days}d` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card p-4 md:p-5">
        <h2 className="text-lg font-semibold">Known infrastructure costs</h2>
        <p className="mt-1 text-sm text-[var(--color-gray-600)]">
          Manual/approximate — Cloud Billing API integration (live per-service spend) is
          planned but not wired up yet. Cloud Run/Cloud SQL request/error/latency metrics
          (Cloud Monitoring API) are the other planned addition, gated on granting the
          API&apos;s service account monitoring.viewer.
        </p>
        <table className="mt-4 w-full max-w-md text-sm">
          <tbody className="divide-y divide-[var(--color-border)]">
            <tr>
              <td className="py-2 text-[var(--color-gray-600)]">Cloud SQL (db-f1-micro)</td>
              <td className="py-2 text-right tabular-nums">~$10/mo</td>
            </tr>
            <tr>
              <td className="py-2 text-[var(--color-gray-600)]">Domain</td>
              <td className="py-2 text-right tabular-nums">$165/yr</td>
            </tr>
            <tr>
              <td className="py-2 text-[var(--color-gray-600)]">Cloud Run</td>
              <td className="py-2 text-right tabular-nums">pay-per-use, low volume</td>
            </tr>
            <tr>
              <td className="py-2 text-[var(--color-gray-600)]">Firebase Hosting</td>
              <td className="py-2 text-right tabular-nums">free tier</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  );
}
