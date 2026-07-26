"use client";

import Link from "next/link";
import { useMemo, useState, useTransition } from "react";
import type { Project } from "@/lib/types";
import { formatDate, formatSf, formatUsd, stateName, typeLabel } from "@/lib/format";
import {
  getCategoriesInCorpus,
  getCountiesForState,
  getStatesInCorpus,
  getStatusesInCorpus,
  getYearsInCorpus,
} from "@/lib/stats";
import { StatusPill } from "./StatusPill";

type Props = {
  projects: Project[];
};

export function ProjectSearch({ projects }: Props) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<string>("all");
  const [status, setStatus] = useState<string>("all");
  const [type, setType] = useState<string>("all");
  const [county, setCounty] = useState<string>("all");
  const [category, setCategory] = useState<string>("all");
  const [year, setYear] = useState<string>("all");
  const [isPending, startTransition] = useTransition();

  const states = useMemo(() => getStatesInCorpus(projects), [projects]);
  const statuses = useMemo(() => getStatusesInCorpus(projects), [projects]);
  const years = useMemo(() => getYearsInCorpus(projects), [projects]);
  const counties = useMemo(
    () =>
      state === "all"
        ? Array.from(new Set(projects.map((p) => p.county).filter(Boolean))).sort()
        : getCountiesForState(projects, state),
    [projects, state],
  );
  const categories = useMemo(() => getCategoriesInCorpus(projects), [projects]);

  const types = useMemo(
    () => Array.from(new Set(projects.map((p) => p.project_type))).sort(),
    [projects],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return projects.filter((p) => {
      if (state !== "all" && (p.state ?? "GA") !== state) return false;
      if (status !== "all" && p.status !== status) return false;
      if (type !== "all" && p.project_type !== type) return false;
      if (county !== "all" && p.county !== county) return false;
      if (year !== "all" && p.opened_or_announced_date?.slice(0, 4) !== year) return false;
      if (
        category !== "all" &&
        !p.competitor_watch.some((item) =>
          item.toLowerCase().includes(category.toLowerCase()),
        )
      ) {
        return false;
      }
      if (!q) return true;
      const blob = [
        p.id,
        p.name,
        p.city,
        p.county,
        p.owner,
        p.architect,
        p.general_contractor,
        p.description,
        p.opened_or_announced_date ?? "",
        ...p.key_specs,
        ...p.mentioned_brands,
        ...p.competitor_watch,
      ]
        .join(" ")
        .toLowerCase();
      return blob.includes(q);
    });
  }, [projects, query, state, status, type, county, category, year]);

  return (
    <div>
      <div className="card p-4 md:p-5">
        <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
          Search projects
        </label>
        <input
          value={query}
          onChange={(e) => {
            const v = e.target.value;
            startTransition(() => setQuery(v));
          }}
          placeholder="City, owner, GC, HVAC, glazing, healthcare…"
          className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-4 py-3 text-base outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
        />
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <select
            value={state}
            onChange={(e) => {
              setState(e.target.value);
              setCounty("all");
            }}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="all">All states</option>
            {states.map((s) => (
              <option key={s} value={s}>
                {stateName(s)}
              </option>
            ))}
          </select>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="all">All statuses</option>
            {statuses.map((s) => (
              <option key={s} value={s}>
                {s.replaceAll("_", " ")}
              </option>
            ))}
          </select>
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="all">All types</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {typeLabel(t)}
              </option>
            ))}
          </select>
          <select
            value={county}
            onChange={(e) => setCounty(e.target.value)}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="all">All counties</option>
            {counties.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="all">All product categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            value={year}
            onChange={(e) => setYear(e.target.value)}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="all">All years</option>
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>
        <p
          className={`mt-4 text-sm text-[var(--color-gray-600)] ${isPending ? "opacity-60" : ""}`}
        >
          {filtered.length} of {projects.length} projects
        </p>
      </div>

      <ul className="mt-6 divide-y divide-[var(--color-border)] rounded-lg border border-[var(--color-border)] bg-white">
        {filtered.map((project) => (
          <li key={project.id}>
            <Link
              href={`/projects/${project.id}/`}
              className="group block px-4 py-5 transition hover:bg-[var(--color-gray-100)] md:px-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-semibold tracking-tight group-hover:text-[var(--color-green)]">
                      {project.name}
                    </h2>
                    <StatusPill status={project.status} />
                  </div>
                  <p className="mt-1 text-sm text-[var(--color-gray-600)]">
                    <span className="font-mono text-xs text-[var(--color-gray-400)]">
                      {project.id}
                    </span>
                    {" · "}
                    {project.city}
                    {project.county ? `, ${project.county} County` : ""}
                    {project.state ? `, ${stateName(project.state)}` : ""} ·{" "}
                    {typeLabel(project.project_type)}
                    {project.opened_or_announced_date
                      ? ` · ${formatDate(project.opened_or_announced_date)}`
                      : ""}
                  </p>
                </div>
                <div className="text-right text-sm">
                  <p className="font-semibold">{formatUsd(project.estimated_value_usd)}</p>
                  <p className="text-[var(--color-gray-400)]">
                    {formatSf(project.square_footage)}
                  </p>
                </div>
              </div>
              <p className="mt-3 max-w-3xl text-sm leading-relaxed text-[var(--color-gray-600)] line-clamp-2">
                {project.description}
              </p>
            </Link>
          </li>
        ))}
        {filtered.length === 0 && (
          <li className="py-16 text-center text-[var(--color-gray-600)]">
            No projects match. Try a broader city or product category.
          </li>
        )}
      </ul>
    </div>
  );
}
