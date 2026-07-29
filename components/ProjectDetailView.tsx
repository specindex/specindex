"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { StatusPill } from "@/components/StatusPill";
import { ProjectTimeline } from "@/components/ProjectTimeline";
import { ProjectNews } from "@/components/ProjectNews";
import { ProjectLocationMap } from "@/components/ProjectLocationMap";
import { formatDate, formatSf, formatUsd, stateName, typeLabel } from "@/lib/format";
import type { Project } from "@/lib/types";

// Steps reflect what scripts/enrich-project-details.py actually does: a
// search-grounded discovery pass, a second independent pass re-checking
// the highest-stakes claims (see _team_claims / run_crosscheck), and a
// real HTTP HEAD check on every cited news URL (url_resolves()) -- not a
// fixed list of aspirational steps. Labels deliberately don't name the
// underlying model (Gemini) -- an independent design review flagged that
// as "AI theater" that exposes the vendor rather than reading as a
// SpecIndex-owned verification process. Only shown when a project
// actually has enrichment data, since the bar describes that process.
const PIPELINE_STEPS = ["Search-grounded discovery", "Cross-verified (2nd pass)", "Links live-checked"];

// scripts/enrich-project-details.py stores the model name directly in each
// fact's `sources` text (e.g. "Gemini search grounding, Jul 2026"). Real
// provenance, but the same vendor-exposure issue applies to displaying it
// verbatim -- swap the label at render time without touching the stored
// data or the underlying research method.
function displaySource(source: string | null | undefined): string | null {
  if (!source) return source ?? null;
  return source.replace(/\bGemini\b/g, "SpecIndex AI");
}

function PipelineBar() {
  return (
    <div className="card mb-6 flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-xs">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 shrink-0 rounded-full bg-[var(--color-green)]" />
        <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-gray-600)]">
          AI grounding pipeline
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px] text-[var(--color-gray-600)]">
        {PIPELINE_STEPS.map((step, i) => (
          <span key={step} className="flex items-center gap-1.5">
            <span className="rounded border border-[var(--color-green)]/25 bg-[var(--color-green-light)] px-2 py-0.5 font-semibold text-[var(--color-green)]">
              {step}
            </span>
            {i < PIPELINE_STEPS.length - 1 && (
              <span className="text-[var(--color-gray-400)]">→</span>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}

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

function Fact({
  label,
  value,
  mono,
  confidence,
}: {
  label: string;
  value: string;
  mono?: boolean;
  confidence?: string;
}) {
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
        {label}
      </dt>
      <dd className={`mt-1 flex items-center gap-2 text-sm font-medium ${mono ? "font-mono text-xs" : ""}`}>
        {value}
        {confidence && <ConfidenceBadge confidence={confidence} />}
      </dd>
    </div>
  );
}

// The base corpus row for owner/architect/GC can lag behind the enrichment
// pipeline's confirmed team data -- this project is a real example: the
// base row has architect/general_contractor as empty strings while
// enrichment.team has both confirmed. Rather than show "Not reported"
// right above a "Confirmed" answer for the same field further down the
// same page (caught in design review), fall back to the matching team
// fact and show its confidence badge so it's clear where the value came
// from.
function findTeamFact(project: Project, keyPrefix: string) {
  return project.enrichment?.team.find(
    (f) => f.field_key === keyPrefix || f.field_key.startsWith(`${keyPrefix}_`),
  );
}

export function ProjectDetailView({ project }: { project: Project }) {
  const [showBreakdown, setShowBreakdown] = useState(false);
  const scoreRef = useRef<HTMLDivElement>(null);
  const hasEnrichment = Boolean(
    project.enrichment &&
      (project.enrichment.executive_brief.length ||
        project.enrichment.csi_scope.length ||
        project.enrichment.team.length ||
        project.enrichment.contact.length ||
        project.enrichment.permit.length),
  );

  useEffect(() => {
    function onPointerDown(e: MouseEvent) {
      if (scoreRef.current && !scoreRef.current.contains(e.target as Node)) {
        setShowBreakdown(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setShowBreakdown(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

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

      <div className="border-b border-[var(--color-border)] bg-[var(--color-bg)]">
        <div className="mx-auto max-w-6xl px-5 py-8 md:px-8 md:py-10">
          <Link
            href="/projects/"
            className="text-sm font-medium text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
          >
            ← All projects
          </Link>

          {hasEnrichment && (
            <div className="mt-5">
              <PipelineBar />
            </div>
          )}

          <div className="card mt-5 flex flex-col gap-6 p-6 md:p-8 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-3">
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

            {project.score && (
              <div className="relative shrink-0" ref={scoreRef}>
                <div
                  onClick={() => setShowBreakdown((v) => !v)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setShowBreakdown((v) => !v);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  aria-haspopup="true"
                  aria-expanded={showBreakdown}
                  className="flex cursor-pointer items-center gap-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] p-4 shadow-sm transition hover:bg-[var(--color-gray-100)] focus:outline-none focus:ring-2 focus:ring-[var(--color-green)]"
                >
                  <div className="text-center">
                    <div className="font-mono text-3xl font-black tracking-tight text-[var(--color-green)]">
                      {project.score.total}
                      <span className="text-xs font-normal text-[var(--color-gray-400)]">/100</span>
                    </div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-gray-600)]">
                      Priority score
                    </span>
                  </div>
                  <div className="h-10 w-px bg-[var(--color-border)]" />
                  <div className="space-y-1 text-xs">
                    <div className="flex items-center gap-1.5 font-semibold text-[var(--color-green)]">
                      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-green)]" />
                      {project.score.total >= 70
                        ? "High priority"
                        : project.score.total >= 40
                          ? "Watch"
                          : "Low signal"}
                    </div>
                    <div className="text-[11px] text-[var(--color-gray-400)]">Click for breakdown</div>
                  </div>
                </div>

                {showBreakdown && (
                  <div className="absolute right-0 top-full z-50 mt-2 w-64 space-y-3 rounded-xl border border-[var(--color-border)] bg-white p-4 text-xs shadow-xl">
                    <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-2">
                      <strong className="font-bold text-[var(--color-ink)]">Score breakdown</strong>
                      <button
                        onClick={() => setShowBreakdown(false)}
                        aria-label="Close score breakdown"
                        className="text-[var(--color-gray-400)] hover:text-[var(--color-ink)]"
                      >
                        ✕
                      </button>
                    </div>
                    <div className="space-y-2 text-[var(--color-gray-600)]">
                      <div className="flex items-center justify-between">
                        <span>Value</span>
                        <span className="font-mono font-bold text-[var(--color-green)]">
                          {project.score.value}/40
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span>Recency</span>
                        <span className="font-mono font-bold text-[var(--color-green)]">
                          {project.score.recency}/35
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span>News coverage</span>
                        <span className="font-mono font-bold text-[var(--color-green)]">
                          {project.score.news}/25
                        </span>
                      </div>
                    </div>
                    <div className="flex justify-between border-t border-[var(--color-border)] pt-2 font-bold text-[var(--color-ink)]">
                      <span>Total</span>
                      <span className="font-mono text-[var(--color-green)]">{project.score.total} / 100</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 md:px-8 md:py-12 lg:grid-cols-3">
        {/* Main column */}
        <div className="lg:col-span-2">
          {(() => {
            const gcFact = !project.general_contractor
              ? findTeamFact(project, "general_contractor")
              : undefined;
            const architectFact = !project.architect ? findTeamFact(project, "architect") : undefined;
            return (
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
                  value={project.general_contractor || gcFact?.value || "Not reported"}
                  confidence={gcFact?.confidence}
                />
                <Fact
                  label="Architect"
                  value={project.architect || architectFact?.value || "Not reported"}
                  confidence={architectFact?.confidence}
                />
                <Fact
                  label="Brands mentioned"
                  value={
                    project.mentioned_brands.length
                      ? project.mentioned_brands.join(", ")
                      : "None in public seed"
                  }
                />
              </dl>
            );
          })()}

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
                  {displaySource(project.enrichment.executive_brief[0].sources)}
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
                      <p className="mt-1.5 text-xs text-[var(--color-gray-400)]">{displaySource(fact.sources)}</p>
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
            <Link href="/projects/" className="btn btn-outline">
              Back to all projects
            </Link>
          </div>
        </div>

        {/* Sidebar -- reference/lookup content (contacts, permits, documents,
            map, news) lives here rather than stacked under the narrative in
            the left column. Moved here 2026-07-29 after the two columns
            went badly out of balance: every enrichment section had been
            tacked onto the bottom of the left column, leaving the sidebar
            empty for ~1500px below the news card while the left column
            kept going -- exactly the "right column dead space" problem
            already caught and fixed once in the ProjectDetailLight design
            exploration, just not carried over when this real page got
            wired up. */}
        <div className="space-y-6">
          {project.enrichment?.contact.length ? (
            <div className="card p-5">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-gray-400)]">
                Contacts
              </h3>
              <dl className="mt-3 space-y-3">
                {project.enrichment.contact.map((fact) => (
                  <div key={fact.field_key} className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <dt className="text-[10px] font-semibold uppercase tracking-wide text-[var(--color-gray-400)]">
                        {fact.label}
                      </dt>
                      <dd className="mt-0.5 text-sm break-words">{fact.value}</dd>
                    </div>
                    <ConfidenceBadge confidence={fact.confidence} />
                  </div>
                ))}
              </dl>
            </div>
          ) : null}

          {project.enrichment?.permit.length ? (
            <div className="card p-5">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-gray-400)]">
                Permits &amp; filings
              </h3>
              <ul className="mt-3 divide-y divide-[var(--color-border)]">
                {project.enrichment.permit.map((fact) => (
                  <li key={fact.field_key} className="py-2.5 first:pt-0 last:pb-0">
                    <p className="text-sm font-semibold">{fact.label}</p>
                    <p className="mt-0.5 text-xs text-[var(--color-gray-600)]">{fact.value}</p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

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
