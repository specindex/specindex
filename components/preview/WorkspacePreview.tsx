"use client";

import { useState } from "react";
import type { Project } from "@/lib/types";
import { formatDate, formatUsd, toDisplayCase } from "@/lib/format";

// Logged-in workspace preview -- the project record screen (screen 4 of the
// handoff), rendered against the real Maine record.
//
// Local state only. Nothing here writes to the database: notes and stage live
// in useState so the interaction can be judged before any schema work is
// committed to. See docs/logged-in-redesign/ for what production needs.

const STAGES = [
  { key: "watching", label: "Watching", dot: "#8A938C" },
  { key: "engaged", label: "Specifier engaged", dot: "#C0631A" },
  { key: "specified", label: "Spec named", dot: "#16643A" },
  { key: "closed", label: "Closed out", dot: "#5B655E" },
] as const;

type Note = { id: string; kind: string; who: string; when: string; text: string };

export function WorkspacePreview({ project }: { project: Project | null }) {
  const [stage, setStage] = useState<string>("watching");
  const [tracked, setTracked] = useState(true);
  const [draft, setDraft] = useState("");
  const [notes, setNotes] = useState<Note[]>([
    {
      id: "n1", kind: "NOTE", who: "AH", when: "Aug 7",
      text: "Discovery record, no spec yet. This is the whole point of tracking early: when the project manual publishes, we are the first call the specifier gets, not the last.",
    },
  ]);

  if (!project) {
    return <div style={{ padding: 40, fontFamily: "var(--font-sans)" }}>Could not load the demo record.</div>;
  }

  const citations = project.spec_citations ?? [];
  const documents = project.documents ?? [];
  const divisions = project.enrichment?.csi_scope ?? [];
  // Same rule the live record page uses: the dark panel is earned by evidence,
  // never given by default. Gemini's review independently reached the same
  // conclusion -- a dark "success" panel wrapped around zeros makes every
  // record look equally authoritative, so none of them is trusted.
  const hasDepth = documents.length > 0 && citations.length > 0;

  function saveNote() {
    const text = draft.trim();
    if (!text) return;                       // whitespace-only is ignored
    setNotes([{ id: String(Date.now()), kind: "NOTE", who: "AH", when: "now", text }, ...notes]);
    setDraft("");
    setTracked(true);                        // first note also starts tracking
  }

  const shell: React.CSSProperties = {
    fontFamily: "var(--font-sans)", background: "#F5F6F4",
    minHeight: "100vh", color: "#111512",
  };

  return (
    <div style={shell}>
      <div style={{ display: "grid", gridTemplateColumns: "232px minmax(0,1fr)", alignItems: "start" }}>
        {/* ---------------- sidebar ---------------- */}
        <aside style={{
          position: "sticky", top: 0, height: "100vh", background: "#FBFCFB",
          borderRight: "1px solid #E4E7E3", display: "flex", flexDirection: "column", padding: "17px 16px 13px",
        }}>
          <div style={{ fontSize: 16, letterSpacing: "-0.02em", marginBottom: 18 }}>
            <span style={{ fontWeight: 800 }}>Spec</span>
            <span style={{ fontWeight: 600, color: "#3D4A42" }}>Index</span>
          </div>

          <button style={{
            width: "100%", background: "#fff", border: "1px solid #E4E7E3", borderRadius: 9,
            padding: "8px 10px", textAlign: "left", cursor: "pointer", marginBottom: 16,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span style={{ width: 7, height: 7, borderRadius: 999, background: "#16643A" }} />
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 9.5, letterSpacing: "0.08em", color: "#8A938C" }}>
                TERRITORY
              </span>
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, marginTop: 2 }}>Maine</div>
          </button>

          {[["Today", "7"], ["Pipeline", "4"], ["Discover", "412"]].map(([label, n]) => (
            <div key={label} style={{
              height: 33, display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "0 10px", borderRadius: 8, fontSize: 13.5,
              background: label === "Pipeline" ? "#E7EFE9" : "transparent",
              color: label === "Pipeline" ? "#0E4227" : "#3D4A42",
              fontWeight: label === "Pipeline" ? 600 : 500,
            }}>
              <span>{label}</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: label === "Pipeline" ? "#16643A" : "#9AA39D" }}>{n}</span>
            </div>
          ))}

          <div style={{ marginTop: "auto", borderTop: "1px solid #E4E7E3", paddingTop: 12, display: "flex", gap: 9, alignItems: "center" }}>
            <div style={{
              width: 28, height: 28, borderRadius: 999, background: "#16643A", color: "#fff",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700,
            }}>AH</div>
            <div>
              <div style={{ fontSize: 12.5, fontWeight: 600 }}>Asif Hussain</div>
              <div style={{ fontSize: 11, color: "#8A938C" }}>Territory licence</div>
            </div>
          </div>
        </aside>

        {/* ---------------- main ---------------- */}
        <main style={{ maxWidth: 1180, margin: "0 auto", padding: "0 30px 60px", width: "100%" }}>
          <div style={{
            position: "sticky", top: 0, zIndex: 5, height: 56, display: "flex", alignItems: "center",
            gap: 16, background: "rgba(245,246,244,0.94)", backdropFilter: "blur(8px)",
            borderBottom: "1px solid #E4E7E3", marginBottom: 22,
          }}>
            <span style={{ fontSize: 15, fontWeight: 700 }}>Project</span>
            <span style={{
              marginLeft: "auto", height: 31, display: "flex", alignItems: "center", padding: "0 14px",
              borderRadius: 999, background: "#EFF6F1", border: "1px solid #C6DDCF",
              color: "#16643A", fontWeight: 600, fontSize: 13,
            }}>Pipeline · 4</span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 300px", gap: 24, alignItems: "start" }}>
            <div>
              {/* header card */}
              <section style={{ background: "#fff", border: "1px solid #E4E7E3", borderRadius: 12, padding: 22, marginBottom: 16 }}>
                <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12 }}>
                  <span style={{
                    fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.08em",
                    background: "#FBF2E6", color: "#A2601C", padding: "3px 8px", borderRadius: 5,
                  }}>{String(project.status).toUpperCase().replace(/_/g, " ")}</span>
                  <span style={{ fontSize: 13, color: "#5B655E" }}>Institutional · State</span>
                </div>

                <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.025em", margin: "0 0 8px", maxWidth: 620 }}>
                  {toDisplayCase(project.name)}
                </h1>

                {/* The mock rendered "source pulled Not pulled" -- a label glued
                    to a null fallback. Gemini flagged it as reading like an
                    unhandled bug, and it breaks the handoff's own rule against
                    printing anything the source did not state. Drop the whole
                    segment when there is no date rather than narrating its
                    absence. */}
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "#7A857E", marginBottom: 6 }}>
                  {project.spx_id}
                  {project.first_seen_at ? ` · source pulled ${formatDate(project.first_seen_at.slice(0, 10))}` : ""}
                </div>
                <div style={{ fontSize: 13.5, color: "#4B554E" }}>
                  {[project.city, project.state].filter(Boolean).join(", ")}
                </div>

                {/* PROJECT TAKEAWAY -- renamed from "THE READ" after the Gemini
                    exchange. "Specification Summary" would be actively wrong on
                    a record with no specification; "THE READ" reads as
                    editorial jargon in an enterprise tool. This label is
                    honest whether the takeaway is a citation or an absence. */}
                <div style={{
                  marginTop: 18, borderRadius: 12, padding: "18px 20px",
                  background: hasDepth ? "#16643A" : "#F3F8F5",
                  border: hasDepth ? "none" : "1px solid #C6DDCF",
                  color: hasDepth ? "#fff" : "#111512",
                }}>
                  <div style={{
                    fontFamily: "var(--font-mono)", fontSize: 10.5, letterSpacing: "0.09em",
                    color: hasDepth ? "#A8CDB8" : "#16643A", marginBottom: 10,
                  }}>PROJECT TAKEAWAY</div>
                  <p style={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.02em", margin: 0, lineHeight: 1.35 }}>
                    {hasDepth
                      ? `${citations.length} manufacturer${citations.length === 1 ? "" : "s"} named across this project's own specification documents.`
                      : "A discovered project. No specification document has been read yet, so no manufacturer can be named."}
                  </p>

                  {/* Tiles only when at least one is non-zero. A row of 0/0/0
                      under a headline that already said "none" is the same
                      fact three more times. */}
                  {hasDepth && (
                    <div style={{ display: "flex", gap: 10, marginTop: 15 }}>
                      {[
                        [citations.length, "manufacturers cited"],
                        [documents.length, "documents held"],
                        [divisions.length, "divisions in scope"],
                      ].map(([n, label]) => (
                        <div key={String(label)} style={{
                          flex: "1 1 0", background: "rgba(255,255,255,0.09)", borderRadius: 9, padding: "12px 14px",
                        }}>
                          <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-0.02em" }}>{n}</div>
                          <div style={{ fontSize: 12, color: "#C4DDCF", marginTop: 3 }}>{label}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>

              {/* notes -- above the tabs, deliberately */}
              <section style={{
                background: "#fff", border: "1px solid #C6DDCF", borderRadius: 12,
                padding: "18px 20px", boxShadow: "0 1px 2px rgba(17,21,18,0.04)", marginBottom: 16,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <span style={{ fontSize: 15, fontWeight: 700 }}>Log what happened</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "#8A938C" }}>{notes.length}</span>
                  <span style={{ marginLeft: "auto", fontSize: 12, color: "#9AA39D" }}>Private to your territory licence</span>
                </div>

                <div style={{ background: "#FBFCFB", border: "1px solid #E4E7E3", borderRadius: 10, padding: 12 }}>
                  <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") saveNote(); }}
                    placeholder="What happened on the call, who you spoke to, what to do next"
                    style={{
                      width: "100%", minHeight: 62, border: "none", outline: "none", resize: "vertical",
                      background: "transparent", fontFamily: "var(--font-sans)", fontSize: 13.5, color: "#111512",
                    }}
                  />
                  <div style={{ display: "flex", alignItems: "center", marginTop: 8 }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "#9AA39D" }}>⌘ + Enter to save</span>
                    <button onClick={saveNote} style={{
                      marginLeft: "auto", background: "#16643A", color: "#fff", border: "none",
                      borderRadius: 8, padding: "7px 14px", fontSize: 13, fontWeight: 600, cursor: "pointer",
                    }}>Save note</button>
                  </div>
                </div>

                <div style={{ marginTop: 14 }}>
                  {notes.map((n) => (
                    <div key={n.id} style={{ borderLeft: "2px solid #E4E7E3", paddingLeft: 13, marginBottom: 14 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                        <span style={{
                          fontFamily: "var(--font-mono)", fontSize: 10, background: "#F0F2EF",
                          padding: "2px 6px", borderRadius: 5, color: "#5B655E",
                        }}>{n.kind}</span>
                        <span style={{ fontSize: 12, color: "#8A938C" }}>{n.who}</span>
                        <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 11, color: "#9AA39D" }}>{n.when}</span>
                      </div>
                      <p style={{ fontSize: 13.5, color: "#4B554E", lineHeight: 1.6, margin: 0 }}>{n.text}</p>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            {/* ---------------- right rail ---------------- */}
            <aside style={{ position: "sticky", top: 74, display: "flex", flexDirection: "column", gap: 14 }}>
              {/* Score ABOVE pipeline: Gemini's point, and it holds. A rep
                  evaluates fit before deciding a stage. */}
              <div style={{ background: "#fff", border: "1px solid #E4E7E3", borderRadius: 12, padding: 16 }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                  <span style={{
                    fontSize: 28, fontWeight: 800, letterSpacing: "-0.03em",
                    color: project.score ? "#16643A" : "#9AA39D",
                  }}>{project.score ? project.score.total : "--"}</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "#8A938C" }}>/100</span>
                </div>
                <div style={{
                  fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.08em",
                  color: "#8A938C", marginTop: 4,
                }}>PRIORITY SCORE</div>
                {/* Unscored collapses to one line. The mock repeated
                    "not scored" once per component, turning a null into three
                    lines of nothing. */}
                {!project.score && (
                  <div style={{ fontSize: 12.5, color: "#8A938C", marginTop: 8 }}>Not scored yet</div>
                )}
              </div>

              <div style={{
                background: tracked ? "#F3F8F5" : "#fff",
                border: `1px solid ${tracked ? "#C6DDCF" : "#E4E7E3"}`,
                borderRadius: 12, padding: 16,
              }}>
                <div style={{
                  fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.08em",
                  color: "#16643A", marginBottom: 10,
                }}>IN YOUR PIPELINE</div>
                {STAGES.map((s) => (
                  <button key={s.key} onClick={() => { setStage(s.key); setTracked(true); }} style={{
                    width: "100%", display: "flex", alignItems: "center", gap: 9, marginBottom: 6,
                    padding: "9px 11px", borderRadius: 8, cursor: "pointer", textAlign: "left",
                    background: "#fff",
                    border: `1px solid ${stage === s.key && tracked ? "#16643A" : "#E4E7E3"}`,
                    fontWeight: stage === s.key && tracked ? 600 : 400, fontSize: 13,
                    fontFamily: "var(--font-sans)",
                  }}>
                    <span style={{ width: 7, height: 7, borderRadius: 999, background: s.dot }} />
                    {s.label}
                  </button>
                ))}
                {/* The mock had BOTH a "← Back to pipeline" link in the body and
                    a big green "Back to pipeline" button here. Gemini called
                    the duplicate out; the stage buttons above already commit on
                    click, so the button was navigation dressed as a save. */}
                <button onClick={() => setTracked(false)} style={{
                  marginTop: 4, background: "transparent", border: "none", color: "#8A938C",
                  fontSize: 12.5, cursor: "pointer", padding: 0, fontFamily: "var(--font-sans)",
                }}>Untrack</button>
              </div>
            </aside>
          </div>
        </main>
      </div>
    </div>
  );
}
