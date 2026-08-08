"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FIREBASE_AUTH_ENABLED, useFirebaseAuth } from "@/components/FirebaseAuthProvider";
import { AskPanel } from "@/components/AskPanel";
import type { Project } from "@/lib/types";
import {
  fetchTrackedProjects,
  upsertTrackedProject,
  untrackProject,
  readTriageList,
  type TrackedStage,
} from "@/lib/tracking";
import { askAboutProject } from "@/lib/ask";
import type { FeedItem } from "./helpers";

const STAGE_LABELS: Record<TrackedStage, string> = {
  watching: "Watching",
  contacted: "Contacted",
  quoted: "Quoted",
  won: "Won",
  lost: "Lost",
};

// Fetches this one project's tracked state on mount rather than requiring a
// caller to pass down the whole tracked-projects list, since this page is
// reached from many different entry points that don't all have that list in
// scope.
export function PipelineBox({ projectId }: { projectId: string }) {
  const { getToken } = useFirebaseAuth();
  const [stage, setStage] = useState<TrackedStage | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);

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

  async function withRollback(next: TrackedStage | null, write: () => Promise<void>) {
    const previous = stage;
    setStage(next);
    setFailed(false);
    try {
      await write();
    } catch {
      setStage(previous);
      setFailed(true);
    }
  }

  async function track() {
    await withRollback("watching", () => upsertTrackedProject(getToken, projectId, { stage: "watching", note }));
  }
  async function changeStage(next: TrackedStage) {
    await withRollback(next, () => upsertTrackedProject(getToken, projectId, { stage: next, note }));
  }
  async function stopTracking() {
    await withRollback(null, () => untrackProject(getToken, projectId));
  }

  if (!loaded) return null;

  if (!stage) {
    return (
      <div className="flex shrink-0 flex-col items-start gap-1">
        <button
          type="button"
          onClick={track}
          style={{
            fontSize: 14,
            fontWeight: 600,
            color: "var(--sx-ink)",
            border: "1px solid var(--sx-line)",
            background: "#fff",
            padding: "12px 17px",
            borderRadius: 9,
            whiteSpace: "nowrap",
          }}
        >
          + Track this project
        </button>
        {failed && <span style={{ fontSize: 11, color: "#dc2626" }}>Couldn&apos;t save, try again.</span>}
      </div>
    );
  }

  return (
    <div style={{ border: "1px solid var(--sx-line)", background: "var(--sx-page-bg)", borderRadius: 9, padding: 14 }}>
      <span style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "var(--sx-muted)" }}>
        Your pipeline
      </span>
      <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600, color: "var(--sx-forest)" }}>
          <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--sx-green)", display: "block" }} />
          Tracking
        </span>
        <select
          value={stage}
          onChange={(e) => changeStage(e.target.value as TrackedStage)}
          style={{ border: 0, background: "var(--sx-chip)", padding: "4px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600, color: "var(--sx-forest)" }}
        >
          {Object.entries(STAGE_LABELS).map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <button type="button" onClick={stopTracking} style={{ marginTop: 8, fontSize: 11, color: "var(--sx-faint)", background: "none", border: 0, cursor: "pointer" }}>
        Untrack
      </button>
    </div>
  );
}

export function ProjectAskPanel({ projectId }: { projectId: string }) {
  const { getToken } = useFirebaseAuth();
  return (
    <AskPanel
      title="Ask about this project"
      placeholder="e.g. Who's the electrical contractor?"
      onAsk={(question) => askAboutProject(getToken, projectId, question)}
    />
  );
}

export function TriageNav({ projectId }: { projectId: string }) {
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
    <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 12, fontSize: 13.5 }}>
      <button
        type="button"
        disabled={!prevId}
        onClick={() => prevId && router.push(`/project/view/?id=${prevId}`)}
        style={{ fontWeight: 500, color: "var(--sx-muted)", background: "none", border: 0, cursor: prevId ? "pointer" : "default", opacity: prevId ? 1 : 0.3 }}
      >
        ← Prev
      </button>
      <span style={{ fontSize: 12, color: "var(--sx-faint)" }}>
        Item {list.index + 1} of {list.ids.length}
      </span>
      <button
        type="button"
        disabled={!nextId}
        onClick={() => nextId && router.push(`/project/view/?id=${nextId}`)}
        style={{ fontWeight: 500, color: "var(--sx-muted)", background: "none", border: 0, cursor: nextId ? "pointer" : "default", opacity: nextId ? 1 : 0.3 }}
      >
        Next →
      </button>
    </div>
  );
}

// Score box + expandable breakdown popover. The five factors shown are a
// LAYOUT PLACEHOLDER for two of the five rows (news, and a fifth slot) --
// only Value/Recency/Spec position are backed by real scoring inputs today.
// Never invent numbers for the placeholder rows.
export function ScoreCard({ score }: { score: Project["score"] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onPointerDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  const hasScore = Boolean(score);
  const tone = !score ? "#8A9AA8" : score.total >= 70 ? "var(--sx-forest)" : score.total >= 40 ? "var(--sx-amber)" : "#8A9AA8";
  const signal = !score ? "Not pulled" : score.total >= 70 ? "High priority" : score.total >= 40 ? "Watch" : "Low signal";

  return (
    <div ref={ref} style={{ position: "relative", flexShrink: 0 }}>
      <button
        type="button"
        onClick={() => hasScore && setOpen((v) => !v)}
        aria-haspopup="true"
        aria-expanded={open}
        style={{
          textAlign: "left",
          cursor: hasScore ? "pointer" : "default",
          // An unpulled score ("--") gets a quieter, dashed treatment
          // rather than the same solid elevated card a real score gets --
          // otherwise a non-existent metric draws exactly as much visual
          // weight as a real one.
          border: hasScore ? `1px solid ${open ? "var(--sx-green)" : "var(--sx-line)"}` : "1px dashed var(--sx-dashed)",
          background: hasScore ? "#fff" : "transparent",
          borderRadius: 12,
          padding: "14px 16px",
          minWidth: 150,
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: 3 }}>
          <span style={{ fontFamily: "var(--font-display)", fontSize: 31, fontWeight: 700, letterSpacing: -1.4, lineHeight: 1, color: tone }}>
            {score ? score.total : "--"}
          </span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--sx-muted)" }}>/100</span>
        </div>
        <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 1.3, textTransform: "uppercase", color: "var(--sx-muted)", marginTop: 7 }}>
          Priority score
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8 }}>
          <span style={{ width: 7, height: 7, borderRadius: 999, background: tone, display: "block" }} />
          <span style={{ fontSize: 12.5, color: "var(--sx-ink)" }}>{signal}</span>
        </div>
        {hasScore && <div style={{ fontSize: 11.5, color: "var(--sx-muted)", marginTop: 5 }}>Click for breakdown</div>}
      </button>

      {open && score && (
        <div
          style={{
            position: "absolute",
            right: 0,
            top: "100%",
            zIndex: 50,
            marginTop: 8,
            width: 280,
            background: "var(--sx-page-bg)",
            border: "1px solid var(--sx-line)",
            borderRadius: 12,
            padding: "20px 22px",
            boxShadow: "0 20px 40px rgba(12,21,36,0.12)",
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 2, textTransform: "uppercase", color: "var(--sx-muted)", marginBottom: 4 }}>
            What drives this score
          </div>
          <p style={{ fontSize: 13, color: "var(--sx-muted)", margin: "0 0 12px" }}>
            Score reflects how much you can act on, not how big the job is. A small job with a spec book outranks a
            large one without.
          </p>
          {[
            { label: "Value", detail: "Estimated project value", value: `${score.value}/30`, real: true },
            { label: "Recency", detail: "How recently this project surfaced", value: `${score.recency}/25`, real: true },
            {
              label: "Spec position",
              detail: score.position ? "Position found in documents held" : "No manufacturer found in documents held",
              value: `${score.position ?? 0}/45`,
              real: true,
            },
            { label: "News signal", detail: "Layout placeholder, not wired yet", value: "—", real: false },
            { label: "Team confidence", detail: "Layout placeholder, not wired yet", value: "—", real: false },
          ].map((row) => (
            <div key={row.label} style={{ display: "flex", gap: 8, alignItems: "center", padding: "11px 0", borderTop: "1px solid var(--sx-line)" }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14.5, fontWeight: 600, marginBottom: 2 }}>{row.label}</div>
                <div style={{ fontSize: 13, color: "var(--sx-muted)", lineHeight: 1.45 }}>{row.detail}</div>
              </div>
              <div style={{ flexShrink: 0, fontFamily: "var(--font-mono)", fontSize: 12.5, color: row.real ? "var(--sx-green)" : "var(--sx-faint)" }}>
                {row.value}
              </div>
            </div>
          ))}
          <div
            style={{
              marginTop: 12,
              border: "1px dashed var(--sx-dashed)",
              borderRadius: 9,
              padding: "12px 14px",
              fontSize: 12.5,
              lineHeight: 1.55,
              color: "var(--sx-muted)",
            }}
          >
            <strong style={{ color: "var(--sx-ink)" }}>Template placeholder.</strong> News signal and team confidence
            are a layout stand-in, not the live scoring model.
          </div>
        </div>
      )}
    </div>
  );
}

// Shows/hides the five server-rendered tab panels via CSS rather than
// mounting/unmounting content, so every tab's content stays in the initial
// server HTML for indexing while the visible page still behaves like tabs.
const TAB_KEYS = ["brief", "scope", "spec", "team", "documents"] as const;
export type TabKey = (typeof TAB_KEYS)[number];

export function TabBar({ counts }: { counts: Record<TabKey, number> }) {
  const [active, setActive] = useState<TabKey>("brief");

  useEffect(() => {
    for (const key of TAB_KEYS) {
      const panel = document.getElementById(`tab-panel-${key}`);
      if (panel) panel.style.display = key === active ? "" : "none";
    }
  }, [active]);

  const labels: Record<TabKey, string> = {
    brief: "Executive brief",
    scope: "Scope",
    spec: "Specification",
    team: "Team",
    documents: "Documents",
  };

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 2, padding: "0 18px", borderBottom: "1px solid var(--sx-line)" }}>
      {TAB_KEYS.map((key) => (
        <button
          key={key}
          type="button"
          onClick={() => setActive(key)}
          style={{
            padding: "16px 13px",
            fontSize: 14.5,
            fontWeight: 600,
            background: "none",
            border: 0,
            cursor: "pointer",
            color: active === key ? "var(--sx-ink)" : "var(--sx-muted)",
            boxShadow: active === key ? "inset 0 -2px 0 var(--sx-forest)" : "none",
            display: "flex",
            alignItems: "center",
            gap: 7,
          }}
        >
          {labels[key]}
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              padding: "1px 7px",
              borderRadius: 999,
              background: counts[key] > 0 ? "var(--sx-chip)" : "var(--sx-page-bg)",
              color: counts[key] > 0 ? "var(--sx-forest)" : "var(--sx-faint)",
            }}
          >
            {counts[key]}
          </span>
        </button>
      ))}
    </div>
  );
}

export function ActivityFeed({ items }: { items: FeedItem[] }) {
  const [filter, setFilter] = useState<"ALL" | "AI_SIGNAL" | "NEWS">("ALL");
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
              {item.time && <span className="shrink-0 font-mono text-[10px] text-[var(--color-gray-400)]">{item.time}</span>}
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
            {item.body && <p className="mt-1 text-xs leading-relaxed text-[var(--color-gray-600)]">{item.body}</p>}
          </div>
        ))}
        {filtered.length === 0 && <p className="py-4 text-center text-xs text-[var(--color-gray-400)]">Nothing in this filter yet.</p>}
      </div>
    </div>
  );
}

// Purely presentational -- ProjectDetailUpgrade below owns the actual
// fetch-and-swap. Driven directly off the CURRENT project's own `gated`
// flag rather than separate auth-loading/upgraded flags: once the upgrade
// swaps in a real full record, that record's `gated` is false and this
// disappears as a natural consequence of the data changing, not a second
// piece of state that has to agree with the first.
export function GatedBanner() {
  return (
    <div className="mt-5 rounded-lg border border-[var(--color-amber)] bg-[#fffbeb] p-4 text-sm text-[var(--color-ink)]">
      You&apos;re seeing the public summary. Sign in to see estimated value, square footage, owner, architect,
      general contractor, and sourced documents for this project.
    </div>
  );
}

// The static build only ever bakes in the public teaser (unauthenticated
// build-time fetch, see lib/projects.ts's X-Build-Token path) -- a signed-in
// visitor's session has no effect on that HTML. This wraps the whole
// server-rendered ProjectDetailView tree and, once a signed-in fetch
// returns the full record, swaps `project` wholesale and lets React
// re-render everything from the real data (citations, documents, facts,
// the read panel's deep/shallow flip) -- not just a banner. ProjectDetailView
// itself has no "use client" and does no server-only work, so it renders
// fine inside this client boundary; Next bundles it for the browser once
// it's reached from here, same as any other client-tree import.
export { FIREBASE_AUTH_ENABLED };
