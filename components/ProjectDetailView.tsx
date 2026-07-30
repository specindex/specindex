"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/clerk-react";
import { CLERK_ENABLED } from "@/components/ClerkProviders";
import { StatusPill } from "@/components/StatusPill";
import { AskPanel } from "@/components/AskPanel";
import { formatDate, formatSf, formatUsd, stateName, typeLabel } from "@/lib/format";
import type { Project } from "@/lib/types";
import {
  fetchTrackedProjects,
  upsertTrackedProject,
  untrackProject,
  readTriageList,
  type TrackedStage,
} from "@/lib/tracking";
import { askAboutProject } from "@/lib/ask";

const STAGE_LABELS: Record<TrackedStage, string> = {
  watching: "Watching",
  contacted: "Contacted",
  quoted: "Quoted",
  won: "Won",
  lost: "Lost",
};

// Small, self-contained: fetches this one project's tracked state on mount
// rather than requiring a caller to pass down the whole tracked-projects
// list, since ProjectDetailView is reached from many different entry points
// (static SSG pages, the client-rendered fallback, direct links) that don't
// all have that list in scope.
function PipelineBox({ projectId }: { projectId: string }) {
  const { getToken } = useAuth();
  const [stage, setStage] = useState<TrackedStage | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchTrackedProjects(getToken)
      .then((rows) => {
        if (cancelled) return;
        const match = rows.find((r) => r.project_id === projectId);
        setStage(match?.stage ?? null);
        setNote(match?.note ?? null);
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
    return () => {
      cancelled = true;
    };
  }, [getToken, projectId]);

  async function track() {
    setStage("watching");
    await upsertTrackedProject(getToken, projectId, { stage: "watching", note });
  }

  async function changeStage(next: TrackedStage) {
    setStage(next);
    await upsertTrackedProject(getToken, projectId, { stage: next, note });
  }

  async function stopTracking() {
    setStage(null);
    await untrackProject(getToken, projectId);
  }

  if (!loaded) return null;

  if (!stage) {
    return (
      <button
        type="button"
        onClick={track}
        className="flex shrink-0 items-center gap-2 rounded-xl border border-dashed border-[var(--color-border)] p-4 text-sm font-semibold text-[var(--color-gray-600)] transition hover:border-[var(--color-green)] hover:text-[var(--color-green)]"
      >
        + Track this project
      </button>
    );
  }

  return (
    <div className="shrink-0 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
      <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-gray-600)]">
        Your pipeline
      </span>
      <div className="mt-2 flex items-center gap-2">
        <span className="flex items-center gap-1.5 text-xs font-semibold text-[var(--color-green)]">
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-green)]" />✓ Tracking
        </span>
        <select
          value={stage}
          onChange={(e) => changeStage(e.target.value as TrackedStage)}
          className="rounded-full border-0 bg-[var(--color-green-light)] px-2.5 py-1 text-xs font-semibold text-[var(--color-green)]"
        >
          {Object.entries(STAGE_LABELS).map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <button
        type="button"
        onClick={stopTracking}
        className="mt-2 text-[11px] text-[var(--color-gray-400)] hover:text-red-600"
      >
        Untrack
      </button>
    </div>
  );
}

// useAuth() requires a <ClerkProvider> ancestor, which only exists when
// CLERK_ENABLED -- kept in its own component (only mounted behind that
// flag, same pattern as PipelineBox above) rather than called directly in
// ProjectDetailView's body, which renders unconditionally.
function ProjectAskPanel({ projectId }: { projectId: string }) {
  const { getToken } = useAuth();
  return (
    <AskPanel
      title="Ask about this project"
      placeholder="e.g. Who's the electrical contractor?"
      onAsk={(question) => askAboutProject(getToken, projectId, question)}
    />
  );
}

// Prev/Next nav across whatever list a signed-in visitor arrived from (Feed
// or Tracked), so triaging several projects in a row doesn't require
// bouncing back to the list view each time. Reads a sessionStorage snapshot
// SignedInHome writes on click-through (lib/tracking.ts's
// writeTriageList/readTriageList) -- absent entirely for anyone who didn't
// arrive that way (direct link, search, anonymous SSG page), in which case
// this renders nothing rather than a broken/empty nav.
function TriageNav({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [list, setList] = useState<{ ids: string[]; index: number } | null>(null);

  useEffect(() => {
    const stored = readTriageList();
    if (!stored || !stored.ids.includes(projectId)) return;
    setList({ ids: stored.ids, index: stored.ids.indexOf(projectId) });
  }, [projectId]);

  if (!list || list.ids.length < 2) return null;

  const prevId = list.index > 0 ? list.ids[list.index - 1] : null;
  const nextId = list.index < list.ids.length - 1 ? list.ids[list.index + 1] : null;

  return (
    <div className="mt-3 flex items-center gap-3 text-sm">
      <button
        type="button"
        disabled={!prevId}
        onClick={() => prevId && router.push(`/projects/view/?id=${prevId}`)}
        className="font-medium text-[var(--color-gray-600)] hover:text-[var(--color-ink)] disabled:opacity-30"
      >
        ← Prev
      </button>
      <span className="text-xs text-[var(--color-gray-400)]">
        Item {list.index + 1} of {list.ids.length}
      </span>
      <button
        type="button"
        disabled={!nextId}
        onClick={() => nextId && router.push(`/projects/view/?id=${nextId}`)}
        className="font-medium text-[var(--color-gray-600)] hover:text-[var(--color-ink)] disabled:opacity-30"
      >
        Next →
      </button>
    </div>
  );
}

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

function PipelineBar({ checkedAt }: { checkedAt: string | null | undefined }) {
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
      {/* Real timestamp from project_enrichment_checks.checked_at -- when
          this run last happened, not a fabricated freshness claim. */}
      {checkedAt && (
        <span className="text-[11px] text-[var(--color-gray-400)]">
          Page updated {formatDate(checkedAt.slice(0, 10))}
        </span>
      )}
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

// Same information as ConfidenceBadge, quieter presentation -- a filled
// pill on every row of a dense list (e.g. every contact) was flagged in
// design review as "badge fatigue": once every item has a high-contrast
// background, none of them read as a highlight anymore. A small dot plus
// plain text carries the same signal without the visual weight.
function ConfidenceDot({ confidence }: { confidence: string }) {
  const dotCls: Record<string, string> = {
    confirmed: "bg-[var(--color-green)]",
    reported: "bg-[var(--color-amber)]",
    unconfirmed: "bg-[var(--color-gray-400)]",
  };
  const textCls: Record<string, string> = {
    confirmed: "text-[var(--color-green)]",
    reported: "text-[var(--color-amber)]",
    unconfirmed: "text-[var(--color-gray-400)]",
  };
  const labels: Record<string, string> = {
    confirmed: "Confirmed",
    reported: "Sources vary",
    unconfirmed: "Not confirmed",
  };
  return (
    <span className={`flex shrink-0 items-center gap-1 text-[10px] font-semibold uppercase tracking-wide ${textCls[confidence] ?? textCls.unconfirmed}`}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotCls[confidence] ?? dotCls.unconfirmed}`} />
      {labels[confidence] ?? confidence}
    </span>
  );
}

const EMPTY_FACT_VALUES = new Set(["Not reported", "None found yet"]);

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
  // A missing value in the same bordered cell as a real one ($5B next to
  // "Not reported") gave both equal visual weight -- flagged in design
  // review as dead-ending the reader's scan path. Muting it keeps the
  // layout stable (still a cell, still there) without competing for
  // attention with actual data.
  const isEmpty = EMPTY_FACT_VALUES.has(value);
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3">
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
        {label}
      </dt>
      <dd
        className={`mt-1 text-sm font-medium ${mono ? "font-mono text-xs" : ""} ${
          isEmpty ? "text-[var(--color-gray-400)] font-normal" : ""
        }`}
      >
        {/* Badge stacked below the value, not centered beside it -- a
            long value (e.g. "Hyundai Engineering America, Inc.")
            wraps to several lines in these narrow KPI cells, and
            items-center was vertically centering the badge against
            that whole wrapped block instead of sitting cleanly with
            it. Stacking keeps the badge inside the box regardless of
            how many lines the value wraps to. */}
        <span className="break-words">{value}</span>
        {confidence && (
          <span className="mt-1.5 block w-fit">
            <ConfidenceBadge confidence={confidence} />
          </span>
        )}
      </dd>
    </div>
  );
}

// Same green/amber/gray tier scale ProjectScoreBadge used before the score
// moved into the hero card -- shared so the sticky bar (visible from the
// moment the page loads) and the hero's own score box never disagree on
// what color a given score means, which an independent design review
// flagged as exactly this kind of mismatch.
function scoreTier(total: number) {
  if (total >= 70) {
    return {
      label: "High priority",
      textCls: "text-[var(--color-green)]",
      dotCls: "bg-[var(--color-green)]",
      chipCls: "bg-[var(--color-green-light)] text-[var(--color-green)]",
    };
  }
  if (total >= 40) {
    return {
      label: "Watch",
      textCls: "text-[var(--color-amber)]",
      dotCls: "bg-[var(--color-amber)]",
      chipCls: "bg-[var(--color-amber)]/10 text-[var(--color-amber)]",
    };
  }
  return {
    label: "Low signal",
    textCls: "text-[var(--color-gray-600)]",
    dotCls: "bg-[var(--color-gray-400)]",
    chipCls: "bg-[var(--color-gray-100)] text-[var(--color-gray-600)]",
  };
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

const TIMELINE_EVENT_LABELS: Record<string, string> = {
  Announced: "Announced",
  Design_Started: "Design started",
  Permit_Issued: "Permit issued",
  Bid_Opened: "Bid opened",
  Awarded: "Awarded",
  Groundbroken: "Groundbroken",
};

type FeedItem = {
  id: string;
  type: "AI_SIGNAL" | "NEWS";
  source: string;
  time: string;
  title: string;
  url?: string | null;
  body?: string | null;
};

// The artifact's "Workspace & Activity Feed" mixes two real, already-
// fetched sources into one filterable timeline rather than each living in
// its own disconnected section: project.timeline (permit/bid/award
// milestones, real dates) and enrichment.permit (filings without dates)
// become AI_SIGNAL entries; project.news becomes NEWS entries. This is
// the same content previously split across a standalone Timeline section
// and a standalone "Related news" sidebar card -- merged here to match
// the artifact's exact section list instead of carrying both old and new
// versions of the same information.
function buildFeedItems(project: Project): FeedItem[] {
  const signals: FeedItem[] = [
    ...project.timeline.map((t, i) => ({
      id: `timeline-${i}-${t.event_type}`,
      type: "AI_SIGNAL" as const,
      source: t.source_name,
      time: formatDate(t.event_date ?? undefined),
      title: TIMELINE_EVENT_LABELS[t.event_type] ?? t.event_type,
      url: t.source_url,
      body: null,
    })),
    ...(project.enrichment?.permit ?? []).map((f) => ({
      id: `permit-${f.field_key}`,
      type: "AI_SIGNAL" as const,
      source: "Permit filing",
      time: "",
      title: f.label,
      url: null,
      body: f.value,
    })),
  ];
  const news: FeedItem[] = project.news.map((n) => ({
    id: `news-${n.url}`,
    type: "NEWS" as const,
    source: n.source_name ?? "News",
    time: n.published_at ? formatDate(n.published_at.slice(0, 10)) : "",
    title: n.title,
    url: n.url,
    body: null,
  }));
  return [...signals, ...news];
}

function ActivityFeed({ project }: { project: Project }) {
  const [filter, setFilter] = useState<"ALL" | "AI_SIGNAL" | "NEWS">("ALL");
  const items = buildFeedItems(project);
  if (items.length === 0) return null;
  const filtered = items.filter((item) => filter === "ALL" || item.type === filter);

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--color-border)] pb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-gray-400)]">
          Workspace &amp; activity feed
        </h3>
        <div className="flex items-center gap-0.5 rounded-lg bg-[var(--color-gray-100)] p-0.5 text-[10px] font-semibold">
          {(["ALL", "AI_SIGNAL", "NEWS"] as const).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              aria-pressed={filter === f}
              className={`rounded-md px-2 py-1 transition ${
                filter === f ? "bg-white text-[var(--color-ink)] shadow-sm" : "text-[var(--color-gray-600)]"
              }`}
            >
              {f === "ALL" ? "All" : f === "AI_SIGNAL" ? "AI Signals" : "News"}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-3 space-y-3">
        {filtered.map((item) => (
          <div
            key={item.id}
            className={`rounded-lg border p-3 text-xs ${
              item.type === "AI_SIGNAL"
                ? "border-[var(--color-green)]/20 bg-[var(--color-green-light)]/30"
                : "border-[var(--color-border)] bg-[var(--color-bg)]"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold text-[var(--color-ink)]">{item.source}</span>
              {item.time && (
                <span className="shrink-0 font-mono text-[10px] text-[var(--color-gray-400)]">{item.time}</span>
              )}
            </div>
            {item.url ? (
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 flex items-start gap-1 text-xs font-medium leading-snug text-blue-600 hover:text-blue-700 hover:underline"
              >
                {item.title}
                <span className="shrink-0 text-[var(--color-gray-400)]">↗</span>
              </a>
            ) : (
              <p className="mt-1 text-xs font-medium leading-snug text-[var(--color-ink)]">{item.title}</p>
            )}
            {item.body && (
              <p className="mt-1 text-xs leading-relaxed text-[var(--color-gray-600)]">{item.body}</p>
            )}
          </div>
        ))}
        {filtered.length === 0 && (
          <p className="py-4 text-center text-xs text-[var(--color-gray-400)]">Nothing in this filter yet.</p>
        )}
      </div>
    </div>
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
  const gcFact = !project.general_contractor ? findTeamFact(project, "general_contractor") : undefined;
  const architectFact = !project.architect ? findTeamFact(project, "architect") : undefined;

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
            <span
              className={`flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${scoreTier(project.score.total).chipCls}`}
            >
              <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${scoreTier(project.score.total).dotCls}`} />
              {project.score.total}/100
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

          {CLERK_ENABLED && <TriageNav projectId={project.id} />}

          {project.gated && (
            <div className="mt-5 rounded-lg border border-[var(--color-amber)] bg-[#fffbeb] p-4 text-sm text-[var(--color-ink)]">
              You&apos;re seeing the public summary. Sign in to see estimated value,
              square footage, owner, architect, general contractor, and sourced
              documents for this project.
            </div>
          )}

          {hasEnrichment && (
            <div className="mt-5">
              <PipelineBar checkedAt={project.enrichment?.checked_at} />
            </div>
          )}

          <div className="card mt-5 space-y-6 p-6 md:p-8">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <StatusPill status={project.status} />
                  <span className="text-sm text-[var(--color-gray-600)]">
                    {typeLabel(project.project_type)}
                  </span>
                </div>
                <h1 className="mt-3 text-2xl font-bold tracking-tight text-[var(--color-ink)] sm:text-3xl">
                  {project.name}
                </h1>
                <p className="mt-2 font-mono text-xs text-[var(--color-gray-400)]">
                  {project.spx_id}
                  {/* Real project_sources ingestion date -- when SpecIndex
                      last pulled/re-loaded this project's record from its
                      original public source, distinct from the AI
                      enrichment pipeline's own "page updated" timestamp
                      shown above in PipelineBar. */}
                  {project.first_seen_at && (
                    <span className="ml-2 text-[var(--color-gray-400)]">
                      · Source data pulled {formatDate(project.first_seen_at.slice(0, 10))}
                    </span>
                  )}
                </p>
                <p className="mt-2 text-sm text-[var(--color-gray-600)]">
                  {project.city}
                  {project.county ? `, ${project.county} County` : ""},{" "}
                  {stateName(project.state)}
                </p>
              </div>

              <div className="flex shrink-0 items-start gap-3">
              {project.score && (() => {
                const tier = scoreTier(project.score.total);
                return (
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
                        <div className={`font-mono text-3xl font-black tracking-tight ${tier.textCls}`}>
                          {project.score.total}
                          <span className="text-xs font-normal text-[var(--color-gray-400)]">/100</span>
                        </div>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-gray-600)]">
                          Priority score
                        </span>
                      </div>
                      <div className="h-10 w-px bg-[var(--color-border)]" />
                      <div className="space-y-1 text-xs">
                        <div className={`flex items-center gap-1.5 font-semibold ${tier.textCls}`}>
                          <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${tier.dotCls}`} />
                          {tier.label}
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
                );
              })()}
              {CLERK_ENABLED && <PipelineBox projectId={project.id} />}
              </div>
            </div>

            {/* KPI grid -- moved in from a standalone "Fact grid" section
                to live inside the hero card, matching the artifact's exact
                layout (title+score row, then a KPI strip underneath,
                nothing else in between). */}
            <dl className="grid grid-cols-2 gap-3 border-t border-[var(--color-border)] pt-6 text-xs md:grid-cols-3 lg:grid-cols-6">
              <Fact label="Project ID" value={project.spx_id} mono />
              <Fact label="Estimated value" value={formatUsd(project.estimated_value_usd)} />
              <Fact label="Square footage" value={formatSf(project.square_footage)} />
              <Fact label="Opened / announced" value={formatDate(project.opened_or_announced_date)} />
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
                    : "None found yet"
                }
              />
            </dl>
          </div>
        </div>
      </div>

      {/* Two-column workspace layout -- left carries the narrative
          (executive brief, CSI scope, team), right is the lookup rail
          (activity feed, permits, contacts). 7/5 split matches the
          ProjectDetailLight design artifact exactly, rather than the
          8/4-ish "content column + sidebar" split this page used before. */}
      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 md:px-8 md:py-12 lg:grid-cols-12">
        {/* LEFT: narrative */}
        <div className="lg:col-span-7 space-y-8">
          {/* Raw corpus description/key-specs only stand in for the
              enrichment pipeline's executive brief when that hasn't run
              yet for this project -- once it has, the two would say the
              same thing twice, and the artifact this page matches doesn't
              carry both. */}
          {!project.enrichment?.executive_brief.length && (
            <section>
              <h2 className="text-base font-bold">Project overview</h2>
              <p className="mt-3 text-xs leading-relaxed text-[var(--color-gray-600)]">
                {project.description}
              </p>
              {project.key_specs.length > 0 && (
                <ul className="mt-4 list-disc space-y-2 pl-5 text-xs text-[var(--color-gray-600)]">
                  {project.key_specs.map((spec) => (
                    <li key={spec}>{spec}</li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {project.enrichment?.executive_brief.length ? (
            <section>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base font-bold">Executive brief</h2>
                <ConfidenceBadge confidence={project.enrichment.executive_brief[0].confidence} />
              </div>
              <p className="mt-3 text-xs leading-relaxed text-[var(--color-gray-600)]">
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
            <section>
              <h2 className="text-base font-bold">CSI scope matrix</h2>
              <div className="mt-4 space-y-3">
                {project.enrichment.csi_scope.map((fact) => (
                  <div key={fact.field_key} className="card p-4">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-xs font-semibold">{fact.label}</p>
                      <ConfidenceBadge confidence={fact.confidence} />
                    </div>
                    <p className="mt-1.5 text-xs leading-relaxed text-[var(--color-gray-600)]">{fact.value}</p>
                    {fact.sources && (
                      <p className="mt-1.5 text-xs text-[var(--color-gray-400)]">{displaySource(fact.sources)}</p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {project.enrichment?.team.length ? (
            <section>
              <h2 className="text-base font-bold">Verified construction team</h2>
              {/* The section title already says "Verified" -- a green
                  Confirmed pill on every single row was flagged in design
                  review as badge fatigue (every row shouting the same
                  thing the header already said). Only show a badge when
                  a row is the exception to that header, i.e. NOT
                  confirmed -- that's the case actually worth flagging. */}
              <dl className="card mt-4 divide-y divide-[var(--color-border)] p-0">
                {project.enrichment.team.map((fact) => (
                  <div key={fact.field_key} className="flex items-start justify-between gap-3 p-4">
                    <div>
                      <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--color-gray-400)]">
                        {fact.label}
                      </dt>
                      <dd className="mt-1 text-xs">{fact.value}</dd>
                    </div>
                    {fact.confidence !== "confirmed" && <ConfidenceBadge confidence={fact.confidence} />}
                  </div>
                ))}
              </dl>
            </section>
          ) : null}

          <div className="flex flex-wrap gap-3 pt-4">
            <Link href="/projects/" className="btn btn-outline">
              Back to all projects
            </Link>
          </div>
        </div>

        {/* RIGHT: workspace / lookup rail */}
        <div className="lg:col-span-5 space-y-6">
          {CLERK_ENABLED && <ProjectAskPanel projectId={project.id} />}

          <ActivityFeed project={project} />

          {/* Permits used to have their own standalone card here too --
              removed after design review pointed out it repeated the same
              permit facts word-for-word that ActivityFeed already surfaces
              as AI_SIGNAL entries a few dozen pixels above it. */}

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
                      <dd className="mt-0.5 text-xs break-words">{fact.value}</dd>
                    </div>
                    <ConfidenceDot confidence={fact.confidence} />
                  </div>
                ))}
              </dl>
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
                      className="flex items-start gap-2 text-xs text-[var(--color-green)] hover:underline"
                    >
                      <span aria-hidden="true">📄</span>
                      <span className="break-words">{doc.title}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
