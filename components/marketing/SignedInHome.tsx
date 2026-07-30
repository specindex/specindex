"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useFirebaseAuth } from "@/components/FirebaseAuthProvider";
import type { Project } from "@/lib/types";
import { formatUsd, stateName } from "@/lib/format";
import { StatusPill } from "@/components/StatusPill";
import { AskPanel } from "@/components/AskPanel";
import { fetchMyProfile, type UserProfile } from "@/lib/userProfile";
import { askAboutMyTerritory } from "@/lib/ask";
import {
  fetchTrackedProjects,
  upsertTrackedProject,
  untrackProject,
  fetchSavedViews,
  createSavedView,
  deleteSavedView,
  writeTriageList,
  type TrackedProject,
  type TrackedStage,
  type SavedView,
} from "@/lib/tracking";
import { buildQuery } from "@/components/ProjectsDashboard";

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

const STAGE_LABELS: Record<TrackedStage, string> = {
  watching: "Watching",
  contacted: "Contacted",
  quoted: "Quoted",
  won: "Won",
  lost: "Lost",
};

const STAGE_TONES: Record<TrackedStage, string> = {
  watching: "bg-[var(--color-gray-100)] text-[var(--color-gray-600)]",
  contacted: "bg-amber-50 text-amber-900",
  quoted: "bg-[var(--color-green-light)] text-[var(--color-green)]",
  won: "bg-[var(--color-green)] text-white",
  lost: "bg-red-50 text-red-700",
};

function scoreTier(total: number) {
  if (total >= 70) return { label: "High priority", cls: "text-[var(--color-green)]" };
  if (total >= 40) return { label: "Watch", cls: "text-[var(--color-amber)]" };
  return { label: "Low signal", cls: "text-[var(--color-gray-400)]" };
}

type PaneView = "feed" | "tracked";

export function SignedInHome() {
  const { getToken, user } = useFirebaseAuth();

  const [view, setView] = useState<PaneView>("feed");
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [tracked, setTracked] = useState<TrackedProject[]>([]);
  const [trackedLoading, setTrackedLoading] = useState(true);
  const [savedViews, setSavedViews] = useState<SavedView[]>([]);

  const [feedProjects, setFeedProjects] = useState<Project[]>([]);
  const [feedTotal, setFeedTotal] = useState(0);
  const [newThisWeek, setNewThisWeek] = useState<number | null>(null);
  const [feedLoading, setFeedLoading] = useState(true);

  const trackedIds = useMemo(() => new Set(tracked.map((t) => t.project_id)), [tracked]);

  useEffect(() => {
    fetchMyProfile(getToken).then(setProfile).catch(() => {});
  }, [getToken]);

  function reloadTracked() {
    setTrackedLoading(true);
    fetchTrackedProjects(getToken)
      .then(setTracked)
      .catch(() => {})
      .finally(() => setTrackedLoading(false));
  }

  useEffect(reloadTracked, [getToken]);

  useEffect(() => {
    fetchSavedViews(getToken).then(setSavedViews).catch(() => {});
  }, [getToken]);

  useEffect(() => {
    if (!profile) return;
    setFeedLoading(true);
    const territory = profile.territory_states.join(",");
    const qs = buildQuery({ state: territory, category: profile.categories[0], sort: "score", limit: 20 });
    fetch(`${API_BASE}/v1/projects?${qs}`)
      .then((r) => r.json())
      .then((data) => {
        setFeedProjects(data.projects ?? []);
        setFeedTotal(data.total ?? 0);
      })
      .catch(() => {})
      .finally(() => setFeedLoading(false));
    const newQs = buildQuery({ state: territory, new_since_days: 7, limit: 1 });
    fetch(`${API_BASE}/v1/projects?${newQs}`)
      .then((r) => r.json())
      .then((data) => setNewThisWeek(typeof data.total === "number" ? data.total : null))
      .catch(() => {});
  }, [profile]);

  async function toggleTrack(project: Project) {
    if (trackedIds.has(project.id)) {
      await untrackProject(getToken, project.id);
    } else {
      await upsertTrackedProject(getToken, project.id, { stage: "watching", note: null });
    }
    reloadTracked();
  }

  async function changeStage(projectId: string, note: string | null, stage: TrackedStage) {
    await upsertTrackedProject(getToken, projectId, { stage, note });
    reloadTracked();
  }

  async function saveNote(projectId: string, stage: TrackedStage, note: string) {
    await upsertTrackedProject(getToken, projectId, { stage, note: note.trim() || null });
    reloadTracked();
  }

  async function handleUntrack(projectId: string) {
    await untrackProject(getToken, projectId);
    reloadTracked();
  }

  async function handleNewSavedView() {
    const name = window.prompt("Name this saved view", profile?.territory_states.join("/") || "New view");
    if (!name) return;
    await createSavedView(getToken, {
      name,
      territory_states: profile?.territory_states ?? [],
      categories: profile?.categories ?? [],
    });
    fetchSavedViews(getToken).then(setSavedViews).catch(() => {});
  }

  async function handleDeleteSavedView(id: number) {
    await deleteSavedView(getToken, id);
    setSavedViews((prev) => prev.filter((v) => v.id !== id));
  }

  // Firebase's User has displayName (full name from the sign-in provider,
  // e.g. Google), not a separate firstName field like Clerk did -- split on
  // the first space as a reasonable approximation.
  const firstName = user?.displayName?.split(" ")[0] ?? null;
  const territoryLabel =
    profile && profile.territory_states.length > 0
      ? profile.territory_states.map((s) => stateName(s)).join(", ")
      : "your territory";

  return (
    <section className="bg-[var(--color-bg)]">
      <div className="mx-auto flex max-w-6xl gap-8 px-5 py-10 md:px-8">
        {/* Left pane */}
        <aside className="hidden w-56 shrink-0 md:block">
          <nav className="flex flex-col gap-1">
            <button
              type="button"
              onClick={() => setView("feed")}
              className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition ${
                view === "feed" ? "bg-white shadow-sm" : "text-[var(--color-gray-600)] hover:bg-white/60"
              }`}
            >
              Feed
              {newThisWeek !== null && newThisWeek > 0 && (
                <span className="rounded-full bg-[var(--color-green-light)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--color-green)]">
                  {newThisWeek}
                </span>
              )}
            </button>
            <button
              type="button"
              onClick={() => setView("tracked")}
              className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition ${
                view === "tracked" ? "bg-white shadow-sm" : "text-[var(--color-gray-600)] hover:bg-white/60"
              }`}
            >
              Tracked
              {tracked.length > 0 && (
                <span className="rounded-full bg-[var(--color-gray-100)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--color-gray-600)]">
                  {tracked.length}
                </span>
              )}
            </button>
          </nav>

          <div className="mt-8">
            <p className="px-3 text-[10px] font-semibold uppercase tracking-wide text-[var(--color-gray-400)]">
              Saved views
            </p>
            <div className="mt-2 flex flex-col gap-1">
              {savedViews.map((v) => (
                <div
                  key={v.id}
                  className="group flex items-center justify-between rounded-lg px-3 py-1.5 text-sm text-[var(--color-gray-600)] hover:bg-white/60"
                >
                  <span className="truncate">{v.name}</span>
                  <button
                    type="button"
                    onClick={() => handleDeleteSavedView(v.id)}
                    className="hidden text-xs text-[var(--color-gray-400)] hover:text-red-600 group-hover:inline"
                  >
                    Remove
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={handleNewSavedView}
                className="rounded-lg px-3 py-1.5 text-left text-sm text-[var(--color-green)] hover:bg-white/60"
              >
                + New saved view
              </button>
            </div>
          </div>

          <div className="mt-8 border-t border-[var(--color-border)] pt-4">
            <Link
              href="/account/"
              className="flex items-center rounded-lg px-3 py-2 text-sm font-medium text-[var(--color-gray-600)] hover:bg-white/60"
            >
              Account settings
            </Link>
          </div>
        </aside>

        {/* Main pane */}
        <div className="min-w-0 flex-1">
          {view === "feed" ? (
            <FeedView
              firstName={firstName}
              territoryLabel={territoryLabel}
              feedTotal={feedTotal}
              feedLoading={feedLoading}
              feedProjects={feedProjects}
              trackedIds={trackedIds}
              onToggleTrack={toggleTrack}
              getToken={getToken}
            />
          ) : (
            <TrackedView
              tracked={tracked}
              loading={trackedLoading}
              onChangeStage={changeStage}
              onSaveNote={saveNote}
              onUntrack={handleUntrack}
            />
          )}
        </div>
      </div>
    </section>
  );
}

function FeedView({
  firstName,
  territoryLabel,
  feedTotal,
  feedLoading,
  feedProjects,
  trackedIds,
  onToggleTrack,
  getToken,
}: {
  firstName: string | null;
  territoryLabel: string;
  feedTotal: number;
  feedLoading: boolean;
  feedProjects: Project[];
  trackedIds: Set<string>;
  onToggleTrack: (project: Project) => void;
  getToken: (options?: { template?: string }) => Promise<string | null>;
}) {
  return (
    <div>
      <h1 className="text-section">
        {firstName ? `Welcome back, ${firstName}.` : "Welcome back."}
      </h1>
      <p className="mt-2 text-[var(--color-gray-600)]">
        Highest-priority open projects in {territoryLabel}.
      </p>

      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <div className="card p-4">
          <p className="text-2xl font-semibold tabular-nums">{feedTotal}</p>
          <p className="text-xs text-[var(--color-gray-400)]">Projects in your territory</p>
        </div>
        <div className="card p-4">
          <p className="text-2xl font-semibold tabular-nums">{trackedIds.size}</p>
          <p className="text-xs text-[var(--color-gray-400)]">Currently tracked</p>
        </div>
        <Link href="/projects/" className="card flex flex-col justify-center p-4 hover:border-[var(--color-green)]">
          <p className="text-sm font-semibold text-[var(--color-green)]">Search full index →</p>
          <p className="text-xs text-[var(--color-gray-400)]">Filters, map view, all states</p>
        </Link>
      </div>

      <div className="mt-6">
        <AskPanel
          title="Ask about your projects"
          placeholder="e.g. What should I prioritize this week?"
          onAsk={(question) => askAboutMyTerritory(getToken, question)}
        />
      </div>

      <div className="mt-8 flex flex-col gap-3">
        {feedLoading && <p className="text-sm text-[var(--color-gray-400)]">Loading projects…</p>}
        {!feedLoading && feedProjects.length === 0 && (
          <p className="text-sm text-[var(--color-gray-400)]">
            No projects matched your saved territory yet. Try{" "}
            <Link href="/projects/" className="text-[var(--color-green)] underline">
              browsing the full index
            </Link>
            .
          </p>
        )}
        {feedProjects.map((p) => {
          const tier = p.score ? scoreTier(p.score.total) : null;
          const isTracked = trackedIds.has(p.id);
          return (
            <div key={p.id} className="card flex items-center gap-4 p-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <Link
                    href={`/projects/view/?id=${p.id}`}
                    className="truncate font-semibold hover:underline"
                    onClick={() => writeTriageList(feedProjects.map((fp) => fp.id), p.id)}
                  >
                    {p.name}
                  </Link>
                  <StatusPill status={p.status} />
                </div>
                <p className="mt-1 text-sm text-[var(--color-gray-600)]">
                  {p.city}, {p.county} · {formatUsd(p.estimated_value_usd)}
                </p>
              </div>
              {tier && (
                <span className={`shrink-0 text-xs font-semibold ${tier.cls}`}>{tier.label}</span>
              )}
              <button
                type="button"
                onClick={() => onToggleTrack(p)}
                className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  isTracked
                    ? "bg-[var(--color-green-light)] text-[var(--color-green)]"
                    : "border border-[var(--color-border)] text-[var(--color-gray-600)] hover:border-[var(--color-green)] hover:text-[var(--color-green)]"
                }`}
              >
                {isTracked ? "✓ Tracking" : "+ Track"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TrackedView({
  tracked,
  loading,
  onChangeStage,
  onSaveNote,
  onUntrack,
}: {
  tracked: TrackedProject[];
  loading: boolean;
  onChangeStage: (projectId: string, note: string | null, stage: TrackedStage) => void;
  onSaveNote: (projectId: string, stage: TrackedStage, note: string) => void;
  onUntrack: (projectId: string) => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  function startEdit(t: TrackedProject) {
    setEditingId(t.project_id);
    setDraft(t.note ?? "");
  }

  function commitEdit(t: TrackedProject) {
    onSaveNote(t.project_id, t.stage, draft);
    setEditingId(null);
  }

  return (
    <div>
      <h1 className="text-section">Tracked pipeline</h1>
      <p className="mt-2 text-[var(--color-gray-600)]">
        Projects you&apos;re actively working, with your own stage and notes.
      </p>

      {loading && <p className="mt-6 text-sm text-[var(--color-gray-400)]">Loading…</p>}
      {!loading && tracked.length === 0 && (
        <p className="mt-6 text-sm text-[var(--color-gray-400)]">
          Nothing tracked yet. Track a project from the Feed to start building your pipeline.
        </p>
      )}

      {!loading && tracked.length > 0 && (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="px-3 py-2 text-left font-semibold">Project</th>
                <th className="px-3 py-2 text-left font-semibold">Stage</th>
                <th className="px-3 py-2 text-left font-semibold">Note</th>
                <th className="px-3 py-2 text-right font-semibold">Value</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {tracked.map((t) => (
                <tr key={t.project_id} className="border-b border-[var(--color-border)] last:border-0">
                  <td className="px-3 py-3">
                    <Link
                      href={`/projects/view/?id=${t.project_id}`}
                      className="font-semibold hover:underline"
                      onClick={() => writeTriageList(tracked.map((tp) => tp.project_id), t.project_id)}
                    >
                      {t.name}
                    </Link>
                    <p className="text-xs text-[var(--color-gray-400)]">
                      {t.city}, {t.county}
                    </p>
                  </td>
                  <td className="px-3 py-3">
                    <select
                      value={t.stage}
                      onChange={(e) => onChangeStage(t.project_id, t.note, e.target.value as TrackedStage)}
                      className={`rounded-full border-0 px-2.5 py-1 text-xs font-semibold ${STAGE_TONES[t.stage]}`}
                    >
                      {Object.entries(STAGE_LABELS).map(([k, label]) => (
                        <option key={k} value={k}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-3 max-w-[260px]">
                    {editingId === t.project_id ? (
                      <textarea
                        autoFocus
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        onBlur={() => commitEdit(t)}
                        rows={2}
                        className="w-full rounded-md border border-[var(--color-border)] p-1.5 text-xs"
                      />
                    ) : (
                      <button
                        type="button"
                        onClick={() => startEdit(t)}
                        className="w-full text-left text-xs text-[var(--color-gray-600)] hover:underline"
                      >
                        {t.note || <span className="italic text-[var(--color-gray-400)]">+ Add note</span>}
                      </button>
                    )}
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums">{formatUsd(t.estimated_value_usd)}</td>
                  <td className="px-3 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => onUntrack(t.project_id)}
                      className="text-xs text-[var(--color-gray-400)] hover:text-red-600"
                    >
                      Untrack
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
