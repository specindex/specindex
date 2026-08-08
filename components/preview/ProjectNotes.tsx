"use client";

import { useCallback, useEffect, useState } from "react";
import { useFirebaseAuth } from "@/components/FirebaseAuthProvider";
import { fetchTrackedProjects, upsertTrackedProject, type TrackedStage } from "@/lib/tracking";

// Notes on a project record. Real, persisted, and scoped to the signed-in user.
//
// This panel previously held a hardcoded note in local React state, so it
// looked like a working CRM and lost everything on reload.
//
// It now writes user_tracked_projects.note through upsertTrackedProject, the
// same authenticated path the Tracked pane on the signed-in home already uses.
// No migration and no new endpoint were needed: the column, the API and the
// uid scoping all existed. api/main.py filters every /v1/me/* query by the
// firebase uid taken from the verified ID token, so a note is readable only by
// the person who wrote it.
//
// ONE note per project, not a feed. That is the shape the column actually has.
// Rendering a list would imply a history the database cannot keep, and losing a
// call log you believed was saved is worse than never being offered the field.
// The NOTE/CALL/EMAIL selector went with it: kind has nowhere to persist, and a
// control that silently discards its value is worse than no control. A real
// history needs a project_notes child table, which is a deliberate next step
// rather than something to fake here.
//
// This panel must never render into the statically exported /project/* pages,
// which are built with a shared build token and served publicly. It is a client
// component behind a signed-in check for exactly that reason.

const CARD: React.CSSProperties = {
  background: "#fff", border: "1px solid #C6DDCF", borderRadius: 12,
  padding: "18px 20px", boxShadow: "0 1px 2px rgba(17,21,18,0.04)", marginBottom: 16,
};

export function ProjectNotes({
  projectId,
  onTracked,
}: {
  projectId: string;
  onTracked?: () => void;
}) {
  const { getToken, isSignedIn } = useFirebaseAuth();

  const [draft, setDraft] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "idle" | "saving" | "error">("loading");
  const [stage, setStage] = useState<TrackedStage>("watching");

  const load = useCallback(async () => {
    if (!isSignedIn) { setStatus("idle"); return; }
    try {
      const rows = await fetchTrackedProjects(getToken);
      const mine = rows.find((r) => r.project_id === projectId);
      setSaved(mine?.note ?? null);
      setDraft(mine?.note ?? "");
      setSavedAt(mine?.updated_at ?? null);
      if (mine?.stage) setStage(mine.stage);
      setStatus("idle");
    } catch {
      // Distinguished from "no note" on purpose. An unreachable API and an
      // empty field look identical once the error is discarded, and showing an
      // empty box invites a rep to retype a note they already wrote.
      setStatus("error");
    }
  }, [getToken, isSignedIn, projectId]);

  useEffect(() => { void load(); }, [load]);

  async function save() {
    const text = draft.trim();
    setStatus("saving");
    try {
      // Saving a note also starts tracking: upsertTrackedProject creates the
      // row if it does not exist. Writing a note about a project you are not
      // tracking has no meaning here, since the note lives on the tracking row.
      await upsertTrackedProject(getToken, projectId, { stage, note: text || null });
      setSaved(text || null);
      setSavedAt(new Date().toISOString());
      setStatus("idle");
      onTracked?.();
    } catch {
      setStatus("error");
    }
  }

  if (!isSignedIn) {
    return (
      <section style={{ ...CARD, border: "1px solid #E4E7E3" }}>
        <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 6 }}>Log what happened</div>
        <p style={{ fontSize: 13, color: "#8A938C", margin: 0, lineHeight: 1.55 }}>
          Sign in to keep notes on this project. What you learn on a call stays attached to the
          record and is private to your licence.
        </p>
      </section>
    );
  }

  const dirty = draft.trim() !== (saved ?? "");

  return (
    <section style={CARD}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 15, fontWeight: 700 }}>Log what happened</span>
        <span style={{ marginLeft: "auto", fontSize: 12, color: "#9AA39D" }}>
          Private to your territory licence
        </span>
      </div>

      {status === "error" && (
        <p style={{ fontSize: 12.5, color: "#A2601C", margin: "0 0 10px", lineHeight: 1.5 }}>
          We could not reach your notes just now. Do not retype: this is a problem on our side, and
          anything already saved is still there. Reload to try again.
        </p>
      )}

      <div style={{ background: "#FBFCFB", border: "1px solid #E4E7E3", borderRadius: 10, padding: 12 }}>
        <textarea
          value={draft}
          disabled={status === "loading"}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") void save(); }}
          placeholder={status === "loading" ? "Loading your note..." : "What happened on the call, who you spoke to, what to do next"}
          style={{
            width: "100%", minHeight: 62, border: "none", outline: "none", resize: "vertical",
            background: "transparent", fontFamily: "var(--font-sans)", fontSize: 13.5, color: "#111512",
          }}
        />
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 8 }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "#9AA39D" }}>
            Cmd + Enter to save
          </span>
          {savedAt && !dirty && status === "idle" && (
            <span style={{ fontSize: 11.5, color: "#8A938C" }}>
              Saved {new Date(savedAt).toLocaleDateString()}
            </span>
          )}
          <button
            onClick={() => void save()}
            disabled={status === "saving" || status === "loading" || !dirty}
            style={{
              marginLeft: "auto", border: "none", borderRadius: 8, padding: "7px 14px",
              fontSize: 13, fontWeight: 600, fontFamily: "var(--font-sans)",
              cursor: dirty && status === "idle" ? "pointer" : "default",
              background: dirty && status === "idle" ? "#16643A" : "#E4E7E3",
              color: dirty && status === "idle" ? "#fff" : "#8A938C",
            }}
          >
            {status === "saving" ? "Saving..." : "Save note"}
          </button>
        </div>
      </div>

      {/* One note, so this is the saved value rather than a list. Shown only
          when it differs from the draft, otherwise it is the same text twice. */}
      {saved && dirty && (
        <div style={{ marginTop: 14, borderLeft: "2px solid #E4E7E3", paddingLeft: 13 }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#8A938C", marginBottom: 4 }}>
            CURRENTLY SAVED
          </div>
          <p style={{ fontSize: 13.5, color: "#4B554E", lineHeight: 1.6, margin: 0 }}>{saved}</p>
        </div>
      )}
    </section>
  );
}
