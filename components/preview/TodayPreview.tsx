"use client";

import { useState } from "react";
import type { Project } from "@/lib/types";
import { formatUsd, toDisplayCase } from "@/lib/format";

// Today (screen 1), rendered entirely against the real corpus.
//
// This screen previously mixed one real record with three illustrative ones
// from lib/previewSeed.ts. That seed is gone and the file is deleted. Three
// reasons, in ascending order of importance:
//
//   1. Two of the three screens (Discover, Workspace) were already 100% real,
//      so Today was the only thing standing between this design and a
//      production deploy.
//   2. A demo that has to be captioned "1 live record, 3 illustrative" spends
//      the viewer's attention on working out which is which.
//   3. The Brand mentions panel was a compliance defect. CLAUDE.md is explicit:
//      "Do not claim brand-vs-competitor visibility. 166 of 591,618 projects
//      carry any brand mention, and those are tenants, not manufacturers."
//      The panel showed "Acuity Brands, rival" against a fabricated citation.
//      It is REMOVED rather than emptied, because the honest empty state for a
//      claim we may not make is no panel at all.
//
// Where a panel has no backing table yet (notes, pipeline stages), it renders a
// written empty state saying so. The handoff's rule is that an empty state is
// explained, never blank, and it is better to show a rep an honest "not built
// yet" than a number nobody can trace to a document.

const MONO = "var(--font-mono)";
const SANS = "var(--font-sans)";

function scoreStyle(total: number | null) {
  if (total == null) return { bg: "#F0F2EF", fg: "#9AA39D", label: "--" };
  if (total >= 70) return { bg: "#E7EFE9", fg: "#16643A", label: String(total) };
  if (total >= 60) return { bg: "#FBF2E6", fg: "#C0631A", label: String(total) };
  return { bg: "#F0F2EF", fg: "#5B655E", label: String(total) };
}

// Written empty state. Takes a reason, not just a title: "no data" is a fact
// about us, and the user is owed which of the two it is -- nothing happened, or
// we have not built it.
function EmptyPanel({ title, body }: { title: string; body: string }) {
  return (
    <div style={{ padding: "4px 0 2px" }}>
      <div style={{ fontSize: 12.5, fontWeight: 600, color: "#4B554E", marginBottom: 4 }}>{title}</div>
      <p style={{ fontSize: 12, color: "#8A938C", lineHeight: 1.55, margin: 0 }}>{body}</p>
    </div>
  );
}

export function TodayPreview({
  projects,
  total,
  documented,
}: {
  projects: Project[];
  total: number;
  documented: number;
}) {
  const [tracked, setTracked] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState("open");

  const selectedCount = Object.values(selected).filter(Boolean).length;
  const trackedCount = Object.values(tracked).filter(Boolean).length;

  // Priority score desc, nulls last. The handoff's stated default, and it also
  // stops the sparsest record leading the screen: an unscored row at the top
  // reads as "the product has nothing" before anyone scrolls.
  const rows = [...projects]
    .sort((a, b) => (b.score?.total ?? -1) - (a.score?.total ?? -1))
    .slice(0, 8);

  const card: React.CSSProperties = {
    background: "#fff", border: "1px solid #E4E7E3", borderRadius: 12,
  };
  const railTitle: React.CSSProperties = { fontSize: 14.5, fontWeight: 700, letterSpacing: "-0.015em" };

  return (
    <div style={{ fontFamily: SANS, background: "#F5F6F4", minHeight: "100vh", color: "#111512" }}>
      <div style={{ display: "grid", gridTemplateColumns: "232px minmax(0,1fr)", alignItems: "start" }}>
        {/* sidebar */}
        <aside style={{
          position: "sticky", top: 0, height: "100vh", background: "#FBFCFB",
          borderRight: "1px solid #E4E7E3", display: "flex", flexDirection: "column", padding: "17px 16px 13px",
        }}>
          <div style={{ fontSize: 16, letterSpacing: "-0.02em", marginBottom: 18 }}>
            <span style={{ fontWeight: 800 }}>Spec</span><span style={{ fontWeight: 600, color: "#3D4A42" }}>Index</span>
          </div>
          <div style={{ background: "#fff", border: "1px solid #E4E7E3", borderRadius: 9, padding: "8px 10px", marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span style={{ width: 7, height: 7, borderRadius: 999, background: "#16643A" }} />
              <span style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: "0.08em", color: "#8A938C" }}>TERRITORY</span>
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, marginTop: 2 }}>Maine</div>
          </div>
          {([
            ["Today", String(rows.length), true],
            ["Pipeline", String(trackedCount), false],
            ["Discover", String(total), false],
          ] as [string, string, boolean][]).map(([label, n, active]) => (
            <a key={label} href={label === "Discover" ? "/preview/discover/" : undefined} style={{
              height: 33, display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "0 10px", borderRadius: 8, fontSize: 13.5, textDecoration: "none",
              background: active ? "#E7EFE9" : "transparent",
              color: active ? "#0E4227" : "#3D4A42", fontWeight: active ? 600 : 500,
            }}>
              <span>{label}</span>
              <span style={{ fontFamily: MONO, fontSize: 11, color: active ? "#16643A" : "#9AA39D" }}>{n}</span>
            </a>
          ))}

          {/* Saved views had four invented view names with invented counts.
              user_saved_views exists as a table but holds nothing for this
              user, so the honest render is the empty state, not four rows of
              plausible-looking filters. */}
          <div style={{ marginTop: 20, marginBottom: 6, display: "flex", alignItems: "center" }}>
            <span style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: "0.09em", color: "#8A938C" }}>SAVED VIEWS</span>
            <span style={{
              marginLeft: "auto", width: 20, height: 20, borderRadius: 5, border: "1px solid #E4E7E3",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, color: "#8A938C",
            }}>+</span>
          </div>
          <p style={{ fontSize: 11.5, color: "#8A938C", lineHeight: 1.5, margin: "2px 2px 0" }}>
            No saved views yet. Filter Discover, then save it here to get it as a daily digest.
          </p>

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

        {/* main */}
        <main style={{ maxWidth: 1180, padding: "0 34px 60px", width: "100%" }}>
          <div style={{
            position: "sticky", top: 0, zIndex: 5, height: 56, display: "flex", alignItems: "center", gap: 16,
            background: "rgba(245,246,244,0.94)", backdropFilter: "blur(8px)",
            borderBottom: "1px solid #E4E7E3", marginBottom: 18,
          }}>
            <span style={{ fontSize: 15, fontWeight: 700 }}>Today</span>
            <input placeholder="Search projects, owners, brands" style={{
              maxWidth: 380, flex: 1, height: 32, borderRadius: 8, border: "1px solid #E4E7E3",
              padding: "0 12px", fontSize: 13, fontFamily: SANS, background: "#fff",
            }} />
            <span style={{
              marginLeft: "auto", height: 31, display: "flex", alignItems: "center", padding: "0 14px",
              borderRadius: 999, background: "#EFF6F1", border: "1px solid #C6DDCF",
              color: "#16643A", fontWeight: 600, fontSize: 13,
            }}>Pipeline · {trackedCount}</span>
          </div>

          {/* Replaces the DEMO DATA chip. Every row on this screen is a real
              corpus record now, so the disclosure that matters is the opposite
              one: how much of the territory we can actually read. */}
          <div
            title="Every project on this screen is a live record from the corpus. Coverage counts documents we hold and have parsed, not documents that exist."
            style={{
              display: "inline-flex", gap: 7, alignItems: "center", background: "#fff",
              border: "1px solid #C6DDCF", borderRadius: 999, padding: "5px 12px", marginBottom: 18,
              cursor: "default",
            }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: "#16643A" }} />
            <span style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.07em", color: "#16643A" }}>LIVE CORPUS</span>
            {/* Only claims the document count when the build could actually
                see it. This page is statically exported by an UNAUTHENTICATED
                build, so api/main.py serves _to_public_teaser and strips
                document_count. The first production deploy therefore rendered
                "0 with documents held" for a territory where we hold 55, which
                reads as "we have no documents" rather than "this build could
                not see them". Understating our own coverage on the live site is
                worse than omitting the number. */}
            <span style={{ fontSize: 12, color: "#8A938C" }}>
              {documented > 0
                ? `${total} Maine records, ${documented} with documents held`
                : `${total} Maine records`}
            </span>
          </div>

          <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-0.03em", margin: "0 0 8px" }}>
            Good morning, Asif.
          </h1>
          <p style={{ fontSize: 14, color: "#5B655E", maxWidth: 580, margin: "0 0 26px" }}>
            The {rows.length} Maine projects most worth your attention, ranked by how much of the
            spec is still winnable. Not a browse-everything list.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 320px", gap: 24, alignItems: "start" }}>
            {/* left */}
            <div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 10 }}>
                <h2 style={{ fontSize: 16, fontWeight: 700, letterSpacing: "-0.02em", margin: 0 }}>
                  Changed on your tracked projects
                </h2>
              </div>

              {/* The change feed was three fabricated events. Change detection
                  against tracked projects is real work that does not exist
                  yet: it needs a per-user tracking table joined to a diff of
                  the nightly capture. Saying so is more useful than three
                  headlines nobody can click through to. */}
              <div style={{ ...card, marginBottom: 26, padding: 16 }}>
                <EmptyPanel
                  title="Nothing to report yet"
                  body="Track a project below and changes to it show up here: a new addendum, a bid date moving, a general contractor being named. Overnight change detection runs against projects you track, so this stays empty until you track your first one."
                />
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                <h2 style={{ fontSize: 16, fontWeight: 700, letterSpacing: "-0.02em", margin: 0 }}>
                  New in Maine, spec still open
                </h2>
                <div style={{ marginLeft: "auto", display: "flex", background: "#EBEEE9", borderRadius: 8, padding: 3, gap: 2 }}>
                  {[["open", "Spec still open"], ["soon", "Bid opens soon"]].map(([k, l]) => (
                    <button key={k} onClick={() => setFilter(k)} style={{
                      border: "none", cursor: "pointer", borderRadius: 6, padding: "6px 11px", fontSize: 12.5,
                      fontFamily: SANS,
                      background: filter === k ? "#fff" : "transparent",
                      boxShadow: filter === k ? "0 1px 2px rgba(17,21,18,0.09)" : "none",
                      fontWeight: filter === k ? 600 : 400, color: filter === k ? "#111512" : "#5B655E",
                    }}>{l}</button>
                  ))}
                </div>
              </div>

              {selectedCount > 0 && (
                <div style={{
                  display: "flex", alignItems: "center", gap: 12, background: "#fff",
                  border: "1px solid #16643A", borderRadius: 9, padding: "10px 14px", marginBottom: 10,
                }}>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{selectedCount} selected</span>
                  <button onClick={() => setSelected({})} style={{
                    background: "none", border: "none", color: "#5B655E", fontSize: 12.5, cursor: "pointer", fontFamily: SANS,
                  }}>Clear</button>
                  <button onClick={() => {
                    const n = { ...tracked };
                    Object.keys(selected).forEach((k) => { if (selected[k]) n[k] = true; });
                    setTracked(n); setSelected({});
                  }} style={{
                    marginLeft: "auto", background: "#16643A", color: "#fff", border: "none", borderRadius: 8,
                    padding: "7px 14px", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: SANS,
                  }}>Track {selectedCount} project{selectedCount === 1 ? "" : "s"}</button>
                </div>
              )}

              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {rows.map((p) => {
                  const s = scoreStyle(p.score?.total ?? null);
                  const isTracked = !!tracked[p.id];
                  const docCount = p.document_count ?? 0;
                  const value = p.estimated_value_usd;
                  const specs = (p.key_specs ?? []).slice(0, 3);
                  return (
                    <div key={p.id} style={{ ...card, padding: "15px 17px", display: "flex", gap: 16 }}>
                      <input type="checkbox" checked={!!selected[p.id]}
                        onChange={(e) => setSelected({ ...selected, [p.id]: e.target.checked })}
                        style={{ width: 16, height: 16, accentColor: "#16643A", cursor: "pointer", marginTop: 3 }} />

                      <div style={{ width: 44, textAlign: "center", flexShrink: 0 }}>
                        <div style={{
                          background: s.bg, color: s.fg, borderRadius: 8, padding: "6px 0",
                          fontSize: 15, fontWeight: 700,
                        }}>{s.label}</div>
                        <div style={{ fontFamily: MONO, fontSize: 9, color: "#9AA39D", marginTop: 3 }}>
                          {p.score?.total == null ? "EARLY" : "SCORE"}
                        </div>
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <a href={`/project/${p.id}/`} style={{
                          fontSize: 15, fontWeight: 700, color: "#111512", textDecoration: "none", display: "block",
                        }}>{toDisplayCase(p.name)}</a>
                        <div style={{ fontSize: 12.5, color: "#6B756E", marginTop: 3 }}>
                          {[p.city && `${toDisplayCase(p.city)}, ${p.state ?? "ME"}`, p.owner && toDisplayCase(p.owner)]
                            .filter(Boolean).join(" · ")}
                          {docCount > 0 ? ` · ${docCount} document${docCount === 1 ? "" : "s"} held` : " · no documents held yet"}
                        </div>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                          {specs.length > 0 ? specs.map((k) => (
                            <span key={k} style={{
                              fontFamily: MONO, fontSize: 11, background: "#F2F4F1", borderRadius: 5, padding: "3px 7px", color: "#4B554E",
                            }}>{k}</span>
                          )) : (
                            <span style={{
                              fontFamily: MONO, fontSize: 11, background: "#F2F4F1", borderRadius: 5,
                              padding: "3px 7px", color: "#8A938C",
                            }}>Scope not read yet</span>
                          )}
                        </div>
                      </div>

                      <div style={{ width: 128, flexShrink: 0, textAlign: "right" }}>
                        <div style={{ fontSize: 12.5, color: "#7A857E" }}>
                          {toDisplayCase(String(p.status ?? ""))}
                        </div>
                        <div style={{ fontFamily: MONO, fontSize: 13, marginTop: 4, color: value ? "#111512" : "#9AA39D" }}>
                          {value ? formatUsd(value) : "Not pulled"}
                        </div>
                        <button onClick={() => setTracked({ ...tracked, [p.id]: !isTracked })} style={{
                          marginTop: 10, width: "100%", height: 30, borderRadius: 7, fontSize: 12.5,
                          fontWeight: 600, cursor: "pointer", fontFamily: SANS,
                          background: isTracked ? "#EFF6F1" : "#16643A",
                          color: isTracked ? "#16643A" : "#fff",
                          border: isTracked ? "1px solid #C6DDCF" : "none",
                        }}>{isTracked ? "Tracking" : "Track"}</button>
                      </div>
                    </div>
                  );
                })}
              </div>

              <p style={{ fontSize: 12.5, color: "#8A938C", marginTop: 14 }}>
                Showing {rows.length} of {total} Maine records. Scored on how much of the spec is
                still winnable, not on how new the project is.
              </p>
            </div>

            {/* right rail */}
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {/* Notes has no backing table. project_notes does not exist, so
                  there is nothing to read and nothing to write. The panel stays
                  because it is the one CRM affordance in scope, and an empty
                  panel that says what it will hold is a design decision the
                  next migration can fill in. */}
              <div style={{ ...card, border: "1px solid #C6DDCF", padding: 16 }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 10 }}>
                  <span style={railTitle}>Your notes</span>
                  <span style={{ fontFamily: MONO, fontSize: 11, color: "#8A938C" }}>0</span>
                </div>
                <EmptyPanel
                  title="No notes yet"
                  body="Add what you learn on a call and it stays attached to the project record: who specified what, and whether an or-equal is still open. What you know about a job lives here."
                />
              </div>

              <div style={{ ...card, padding: 16 }}>
                <div style={{ ...railTitle, marginBottom: 10 }}>Your pipeline</div>
                {trackedCount > 0 ? (
                  <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "6px 0" }}>
                    <span style={{ width: 7, height: 7, borderRadius: 999, background: "#8A938C" }} />
                    <span style={{ fontSize: 12.5 }}>Watching</span>
                    <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 11.5, color: "#5B655E" }}>{trackedCount}</span>
                  </div>
                ) : (
                  <EmptyPanel
                    title="Nothing tracked yet"
                    body="Track a project and it lands here. Stages are yours to set, so a card moves when you say so."
                  />
                )}
              </div>

              {/* Data freshness removed alongside Brand mentions. The three
                  bars were seeded percentages. v_pipeline_health holds exactly
                  one workflow row and it is 13 days stale, which is not enough
                  to build a territory freshness panel on without inventing the
                  other two. It returns when the telemetry does. */}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
