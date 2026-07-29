"use client";

import Link from "next/link";
import { StatusPill } from "@/components/StatusPill";
import { ProjectScoreBadge } from "@/components/ProjectScoreBadge";
import { ProjectTimeline } from "@/components/ProjectTimeline";
import { ProjectNews } from "@/components/ProjectNews";
import { ProjectLocationMap } from "@/components/ProjectLocationMap";
import { formatDate, formatSf, formatUsd, stateName, typeLabel } from "@/lib/format";
import type { Project } from "@/lib/types";

// Shared render for a single project's detail view -- used by both the
// small curated set of statically-generated pages (app/projects/[id]/page.tsx,
// top ~200 by score, real SEO/JSON-LD) and the client-rendered fallback shell
// (app/projects/view/page.tsx) that serves every other project at any scale.
// One component, one visual source of truth, regardless of which path
// fetched the data or when.

// project_enrichment confidence -> the same green/amber/gray scale used
// elsewhere for "how sure are we" -- amber specifically means two
// independent Gemini passes disagreed, not that anything failed.
function ConfidenceBadge({ confidence }: { confidence: string }) {
  const styles: Record<string, string> = {
    confirmed: "bg-[var(--color-green-light)] text-[var(--color-green)]",
    reported: "bg-[var(--color-amber)]/10 text-[var(--color-amber)]",
    unconfirmed: "bg-[var(--color-gray-100)] text-[var(--color-gray-400)]",
  };
  const labels: Record<string, string> = {
    confirmed: "Confirmed",
    reported: "Sources vary",
    unconfirmed: "Not confirmed",
  };
  return (
    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${styles[confidence] ?? styles.unconfirmed}`}>
      {labels[confidence] ?? confidence}
    </span>
  );
}

function Fact({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
        {label}
      </dt>
      <dd className={`mt-1 text-sm font-medium ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}

export function ProjectDetailView({ project }: { project: Project }) {
  return (
    <article className="bg-[var(--color-bg)]">
      {/* Sticky title+score bar -- stays visible while scrolling the long
          write-up below, so the score and identity don't disappear the
          moment someone starts reading (per docs/ROADMAP.md item 52). */}
      <div className="sticky top-14 z-40 border-b border-[var(--color-border)] bg-white/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-5 py-2.5 md:px-8">
          <p className="truncate text-sm font-medium text-[var(--color-ink)]">{project.name}</p>
          {project.score && (
            <span className="shrink-0 rounded-full bg-[var(--color-amber)]/10 px-2.5 py-1 text-xs font-semibold text-[var(--color-amber)]">
              🔥 {project.score.total}/100
            </span>
          )}
        </div>
      </div>

      <div className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-14">
          <Link
            href="/projects/"
            className="text-sm font-medium text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
          >
            ← All projects
          </Link>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <StatusPill status={project.status} />
            <span className="text-sm text-[var(--color-gray-600)]">
              {typeLabel(project.project_type)}
            </span>
          </div>
          <h1 className="mt-3 text-hero">{project.name}</h1>
          <p className="mt-2 font-mono text-sm text-[var(--color-gray-400)]">
            {project.spx_id}
          </p>
          <p className="mt-2 text-lg text-[var(--color-gray-600)]">
            {project.city}
            {project.county ? `, ${project.county} County` : ""},{" "}
            {stateName(project.state)}
          </p>
        </div>
      </div>

      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 md:px-8 md:py-12 lg:grid-cols-3">
        {/* Main column */}
        <div className="lg:col-span-2">
          <dl className="card grid gap-4 p-6 sm:grid-cols-2">
            <Fact label="Project ID" value={project.spx_id} mono />
            <Fact label="Estimated value" value={formatUsd(project.estimated_value_usd)} />
            <Fact label="Square footage" value={formatSf(project.square_footage)} />
            <Fact
              label="Opened / announced"
              value={formatDate(project.opened_or_announced_date)}
            />
            <Fact label="Owner" value={project.owner || "Not reported"} />
            <Fact
              label="General contractor"
              value={project.general_contractor || "Not reported"}
            />
            <Fact label="Architect" value={project.architect || "Not reported"} />
            <Fact
              label="Brands mentioned"
              value={
                project.mentioned_brands.length
                  ? project.mentioned_brands.join(", ")
                  : "None in public seed"
              }
            />
          </dl>

          <section className="mt-8">
            <h2 className="text-xl font-semibold">Project overview</h2>
            <p className="mt-3 text-base leading-relaxed text-[var(--color-gray-600)]">
              {project.description}
            </p>
          </section>

          <section className="mt-8">
            <h2 className="text-xl font-semibold">Key specs</h2>
            <ul className="mt-4 list-disc space-y-2 pl-5 text-[var(--color-gray-600)]">
              {project.key_specs.map((spec) => (
                <li key={spec}>{spec}</li>
              ))}
            </ul>
          </section>

          {/* AI-enriched sections -- populated by scripts/enrich-project-details.py
              via two independent Gemini search passes; only a handful of
              projects have this yet, so every block below is conditional on
              actually having data rather than showing an empty section. */}
          {project.enrichment?.executive_brief.length ? (
            <section className="mt-8">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-semibold">Executive brief</h2>
                <ConfidenceBadge confidence={project.enrichment.executive_brief[0].confidence} />
              </div>
              <p className="mt-3 text-base leading-relaxed text-[var(--color-gray-600)]">
                {project.enrichment.executive_brief[0].value}
              </p>
              {project.enrichment.executive_brief[0].sources && (
                <p className="mt-2 text-xs text-[var(--color-gray-400)]">
                  {project.enrichment.executive_brief[0].sources}
                </p>
              )}
            </section>
          ) : null}

          {project.enrichment?.csi_scope.length ? (
            <section className="mt-8">
              <h2 className="text-xl font-semibold">CSI scope matrix</h2>
              <div className="mt-4 space-y-3">
                {project.enrichment.csi_scope.map((fact) => (
                  <div key={fact.field_key} className="card p-4">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-semibold">{fact.label}</p>
                      <ConfidenceBadge confidence={fact.confidence} />
                    </div>
                    <p className="mt-1.5 text-sm leading-relaxed text-[var(--color-gray-600)]">{fact.value}</p>
                    {fact.sources && (
                      <p className="mt-1.5 text-xs text-[var(--color-gray-400)]">{fact.sources}</p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {project.enrichment?.team.length ? (
            <section className="mt-8">
              <h2 className="text-xl font-semibold">Verified construction team</h2>
              <dl className="card mt-4 divide-y divide-[var(--color-border)] p-0">
                {project.enrichment.team.map((fact) => (
                  <div key={fact.field_key} className="flex items-start justify-between gap-3 p-4">
                    <div>
                      <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--color-gray-400)]">
                        {fact.label}
                      </dt>
                      <dd className="mt-1 text-sm">{fact.value}</dd>
                    </div>
                    <ConfidenceBadge confidence={fact.confidence} />
                  </div>
                ))}
              </dl>
            </section>
          ) : null}

          {project.enrichment?.permit.length ? (
            <section className="mt-8">
              <h2 className="text-xl font-semibold">Permits &amp; filings</h2>
              <ul className="card mt-4 divide-y divide-[var(--color-border)] p-0">
                {project.enrichment.permit.map((fact) => (
                  <li key={fact.field_key} className="p-4">
                    <p className="text-sm font-semibold">{fact.label}</p>
                    <p className="mt-1 text-sm text-[var(--color-gray-600)]">{fact.value}</p>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {project.enrichment?.contact.length ? (
            <section className="mt-8">
              <h2 className="text-xl font-semibold">Contacts</h2>
              <dl className="card mt-4 divide-y divide-[var(--color-border)] p-0">
                {project.enrichment.contact.map((fact) => (
                  <div key={fact.field_key} className="flex items-start justify-between gap-3 p-4">
                    <div>
                      <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--color-gray-400)]">
                        {fact.label}
                      </dt>
                      <dd className="mt-1 text-sm">{fact.value}</dd>
                    </div>
                    <ConfidenceBadge confidence={fact.confidence} />
                  </div>
                ))}
              </dl>
            </section>
          ) : null}

          <section className="mt-8 rounded-lg bg-[var(--color-green)] p-6 text-white">
            <h2 className="text-lg font-semibold text-[var(--color-amber)]">
              Still open for manufacturers
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-white/90">
              {project.open_for}
            </p>
          </section>

          <section className="mt-8">
            <h2 className="text-xl font-semibold">Manufacturer watch list</h2>
            <ul className="mt-4 flex flex-wrap gap-2">
              {project.competitor_watch.map((item) => (
                <li
                  key={item}
                  className="rounded-full border border-[var(--color-border)] bg-white px-3 py-1.5 text-sm text-[var(--color-gray-600)]"
                >
                  {item}
                </li>
              ))}
            </ul>
          </section>

          <div className="mt-6">
            <ProjectTimeline events={project.timeline} />
          </div>

          <div className="mt-12 flex flex-wrap gap-3">
            <Link
              href={`/visibility/${
                project.competitor_watch[0]
                  ? `?category=${encodeURIComponent(project.competitor_watch[0])}`
                  : ""
              }`}
              className="btn btn-primary"
            >
              Run a brand check for this project
            </Link>
            <Link href="/projects/" className="btn btn-outline">
              Back to all projects
            </Link>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <ProjectScoreBadge score={project.score} />
          {project.documents && project.documents.length > 0 && (
            <div className="card p-5">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-gray-400)]">
                Documents ({project.documents.length})
              </h3>
              <ul className="mt-3 space-y-2">
                {project.documents.map((doc) => (
                  <li key={doc.url}>
                    <a
                      href={doc.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-start gap-2 text-sm text-[var(--color-green)] hover:underline"
                    >
                      <span aria-hidden="true">📄</span>
                      <span className="break-words">{doc.title}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <ProjectLocationMap
            latitude={project.latitude}
            longitude={project.longitude}
            name={project.name}
            city={project.city}
            county={project.county}
            state={project.state}
          />
          <ProjectNews news={project.news} />
        </div>
      </div>
    </article>
  );
}
