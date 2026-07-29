"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { Project } from "@/lib/types";
import { brandMentioned, formatUsd } from "@/lib/format";
import { getVisibilitySnapshot } from "@/lib/stats";
import { StatusPill } from "./StatusPill";

/** Building product manufacturers headquartered in Georgia, by CSI division. */
const demoBrands = [
  { name: "Oldcastle", category: "concrete", hq: "Atlanta · CRH concrete, precast and hardscape, Div 03/04/32" },
  { name: "Belgard", category: "paving", hq: "Atlanta · CRH hardscape and pavers, Div 32" },
  { name: "Acuity Brands", category: "lighting", hq: "Atlanta · lighting, Div 26" },
  { name: "Kawneer", category: "glazing", hq: "Norcross · curtain wall, Div 08" },
  { name: "YKK AP", category: "glazing", hq: "Austell · facade systems, Div 08" },
  { name: "Shaw Industries", category: "flooring", hq: "Dalton · flooring, Div 09" },
  { name: "Interface", category: "flooring", hq: "Atlanta · carpet tile, Div 09" },
  { name: "Rheem", category: "hvac", hq: "Atlanta · HVAC and water heating, Div 23" },
  { name: "TK Elevator", category: "elevators", hq: "Atlanta · elevators, Div 14" },
  { name: "Atlas Roofing", category: "roofing", hq: "Atlanta · roofing and polyiso, Div 07" },
  { name: "Southwire", category: "electrical", hq: "Carrollton · wire and cable, Div 26" },
];

type Props = {
  projects: Project[];
};

// Reads ?category= from the URL on first render (e.g. a "Run a brand
// check" link from a project detail page) without useSearchParams/Suspense
// -- this is a static export, so search params can only be read
// client-side anyway; a plain lazy initializer keeps it simple, same
// SSR-safe-guard pattern as ProjectsDashboard's localStorage reads.
function initialCategoryFromUrl(): string {
  if (typeof window === "undefined") return "lighting";
  const fromUrl = new URLSearchParams(window.location.search).get("category");
  return fromUrl || "lighting";
}

export function VisibilityPanel({ projects }: Props) {
  const [brand, setBrand] = useState("Acuity Brands");
  const [category, setCategory] = useState(initialCategoryFromUrl);

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
            placeholder="e.g. Acuity Brands"
          />
          <p className="mt-3 text-[11px] text-[var(--color-gray-400)]">
            Georgia-based manufacturers to try:
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {demoBrands.map((b) => (
              <button
                key={b.name}
                type="button"
                title={b.hq}
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
          label={`Projects needing ${category || "this category"}`}
          value={String(analysis.categoryHits.length)}
          hint={`${analysis.categoryRate}% of the ${projects.length} projects indexed`}
        />
        <StatCard
          label="Still early enough to influence"
          value={String(analysis.stillOpen.length)}
          hint="In planning or permitting, no manufacturer named"
        />
        <StatCard
          label="Named in public sources"
          value={String(analysis.mentioned.length)}
          hint="Usually low, because permits rarely name manufacturers"
        />
      </div>

      <div className="rounded-lg border border-[var(--color-amber)] bg-[var(--color-amber-light,#fffbeb)] p-4">
        <p className="text-sm font-semibold text-[var(--color-ink)]">
          How to read a zero here
        </p>
        <p className="mt-1.5 text-sm leading-relaxed text-[var(--color-gray-600)]">
          The public record hardly ever says which manufacturer was picked, because
          that gets written in the spec book instead. If the third
          number is zero, it means your brand doesn&apos;t appear in the public record
          we can read. It does not mean you lost the job. Reading spec books is what
          we&apos;re building next, and that is where real mention rates will come
          from. Until then, work off the middle number.
        </p>
      </div>

      <ProjectList
        title="Still early enough to influence"
        subtitle={`Projects needing ${category || "this category"} that are in planning or permitting with no ${brand || "brand"} mention. Start here.`}
        projects={analysis.stillOpen}
        empty={`Nothing needing ${category || "this category"} is in planning or permitting right now.`}
      />
      <ProjectList
        title="Already under construction"
        subtitle="Structure is committed on these, but interiors, finishes and FF&E packages are often still open."
        projects={analysis.opportunities.filter((p) => !analysis.stillOpen.includes(p))}
        empty="Nothing under construction needs this category."
      />
      <ProjectList
        title="Named in public sources"
        subtitle={`Projects where ${brand || "this brand"} already turns up in coverage or in the project record.`}
        projects={analysis.mentioned}
        empty={`${brand || "This brand"} doesn't appear in the public record for any indexed project yet.`}
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
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-ink)] p-5 text-white shadow-sm">
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
