"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { Project } from "@/lib/types";
import { brandMentioned, formatUsd } from "@/lib/format";
import { getVisibilitySnapshot } from "@/lib/stats";
import { StatusPill } from "./StatusPill";

const demoBrands = [
  { name: "Hilton", category: "HVAC" },
  { name: "Hyundai", category: "HVAC" },
  { name: "Costco", category: "refrigeration" },
  { name: "Virgin Hotels", category: "lighting" },
  { name: "Master Wall", category: "insulation" },
  { name: "Evans", category: "dock" },
];

type Props = {
  projects: Project[];
};

export function VisibilityPanel({ projects }: Props) {
  const [brand, setBrand] = useState("Hilton");
  const [category, setCategory] = useState("HVAC");

  const analysis = useMemo(
    () => getVisibilitySnapshot(projects, brand, category),
    [projects, brand, category],
  );

  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="card block p-4">
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
            Your brand
          </span>
          <input
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2.5 outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
            placeholder="e.g. Hilton"
          />
          <div className="mt-3 flex flex-wrap gap-2">
            {demoBrands.map((b) => (
              <button
                key={b.name}
                type="button"
                onClick={() => {
                  setBrand(b.name);
                  setCategory(b.category);
                }}
                className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                  brand === b.name
                    ? "bg-[var(--color-green)] text-white"
                    : "bg-[var(--color-gray-100)] text-[var(--color-gray-600)] hover:bg-[var(--color-gray-200)]"
                }`}
              >
                {b.name}
              </button>
            ))}
          </div>
        </label>
        <label className="card block p-4">
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
            Product category to watch
          </span>
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2.5 outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
            placeholder="e.g. HVAC, glazing, flooring"
          />
        </label>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Mention rate"
          value={`${analysis.rate}%`}
          hint={`${analysis.mentioned.length} of ${projects.length} projects`}
        />
        <StatCard
          label="Category opportunities"
          value={String(analysis.opportunities.length)}
          hint={`Open ${category || "category"} fits without your brand`}
        />
        <StatCard
          label="Category pipeline"
          value={String(analysis.categoryHits.length)}
          hint="Projects watching this product area"
        />
      </div>

      <ProjectList
        title="Mentioned"
        subtitle="Brand hits across public coverage and seeded project fields."
        projects={analysis.mentioned}
        empty={`No mentions yet for ${brand || "this brand"} in the Georgia corpus.`}
      />
      <ProjectList
        title="Opportunity projects"
        subtitle={`Category fit without a ${brand || "brand"} mention — highest-leverage outreach targets.`}
        projects={analysis.opportunities}
        empty="No category opportunities for this filter."
      />
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="card bg-[var(--color-ink)] p-5 text-white">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-white/60">
        {label}
      </p>
      <p className="mt-2 font-mono text-3xl font-bold text-[var(--color-amber)]">
        {value}
      </p>
      <p className="mt-2 text-sm text-white/70">{hint}</p>
    </div>
  );
}

function ProjectList({
  title,
  subtitle,
  projects,
  empty,
}: {
  title: string;
  subtitle: string;
  projects: Project[];
  empty: string;
}) {
  return (
    <section>
      <h2 className="text-xl font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-[var(--color-gray-600)]">{subtitle}</p>
      {projects.length === 0 ? (
        <p className="mt-4 text-sm text-[var(--color-gray-600)]">{empty}</p>
      ) : (
        <ul className="mt-4 divide-y divide-[var(--color-border)] rounded-lg border border-[var(--color-border)] bg-white">
          {projects.map((p) => (
            <li key={p.id}>
              <Link
                href={`/projects/${p.id}/`}
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 hover:bg-[var(--color-gray-100)]"
              >
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{p.name}</span>
                    <StatusPill status={p.status} />
                  </div>
                  <p className="text-sm text-[var(--color-gray-600)]">
                    {p.city} · {formatUsd(p.estimated_value_usd)}
                  </p>
                </div>
                <span className="text-sm font-medium text-[var(--color-green)]">
                  View specs →
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
