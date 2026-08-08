"use client";

import { useState } from "react";
import type { Project } from "@/lib/types";
import { toDisplayCase } from "@/lib/format";
import {
  SEED_PROJECTS, SEED_NOTES, SEED_CHANGES, SEED_STAGES, SEED_MENTIONS, SEED_FRESHNESS,
} from "@/lib/previewSeed";

// Today (screen 1). Mixes the ONE real Maine record with the handoff's
// illustrative ones so the layout can be judged both ways: a sparse record
// and a rich record sitting in the same list. Everything except the Maine
// record is sample data and the banner says so.

const MONO = "var(--font-mono)";
const SANS = "var(--font-sans)";

function scoreStyle(total: number | null) {
  if (total == null) return { bg: "#F0F2EF", fg: "#9AA39D", label: "--" };
  if (total >= 70) return { bg: "#E7EFE9", fg: "#16643A", label: String(total) };
  if (total >= 60) return { bg: "#FBF2E6", fg: "#C0631A", label: String(total) };
  return { bg: "#F0F2EF", fg: "#5B655E", label: String(total) };
}

const TAG_TONE: Record<string, { bg: string; fg: string }> = {
  amber: { bg: "#FBF2E6", fg: "#A2601C" },
  green: { bg: "#E7EFE9", fg: "#16643A" },
  grey: { bg: "#F0F2EF", fg: "#5B655E" },
};

export function TodayPreview({ realProject }: { realProject: Project | null }) {
  const [tracked, setTracked] = useState<Record<string, boolean>>(
    Object.fromEntries(SEED_PROJECTS.filter((p) => p.tracked).map((p) => [p.id, true])),
  );
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState("open");

  const selectedCount = Object.values(selected).filter(Boolean).length;
  const trackedCount = Object.values(tracked).filter(Boolean).length;

  // The real record, shaped like a seed row so one renderer handles both.
  const realRow = realProject && {
    id: realProject.id,
    name: toDisplayCase(realProject.name),
    city: toDisplayCase(realProject.city || ""),
    state: realProject.state ?? "ME",
    owner: "State of Maine",
    score: realProject.score?.total ?? null,
    value: null as string | null,
    docCount: realProject.document_count ?? 0,
    divisions: [] as { code: string; label: string }[],
    urgency: "Discovered Aug 6",
    urgent: false,
    source: "Search-grounded discovery, State of Maine",
    real: true,
  };

  // Priority score desc, nulls last. This is the handoff's own stated default
  // sort, and it also stops the sparsest record leading the screen -- an
  // unscored row at the top reads as "the product has nothing" before anyone
  // scrolls. Sorting by actionable density is not hiding the record; it is
  // still in the list, one row down, labelled honestly.
  const rows = [
    ...(realRow ? [realRow] : []),
    ...SEED_PROJECTS.map((p) => ({
      id: p.id, name: p.name, city: p.city, state: p.state, owner: p.owner,
      score: p.score, value: p.value as string | null, docCount: p.docCount,
      divisions: p.divisions, urgency: p.urgency, urgent: p.urgent,
      source: p.source, real: false,
    })),
  ].sort((a, b) => (b.score ?? -1) - (a.score ?? -1));

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
          {[["Today", "7", true], ["Pipeline", String(trackedCount), false], ["Discover", "138", false]].map(([label, n, active]) => (
            <a key={String(label)} href={label === "Discover" ? "/preview/discover/" : undefined} style={{
              height: 33, display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "0 10px", borderRadius: 8, fontSize: 13.5, textDecoration: "none",
              background: active ? "#E7EFE9" : "transparent",
              color: active ? "#0E4227" : "#3D4A42", fontWeight: active ? 600 : 500,
            }}>
              <span>{label}</span>
              <span style={{ fontFamily: MONO, fontSize: 11, color: active ? "#16643A" : "#9AA39D" }}>{n}</span>
            </a>
          ))}

          <div style={{ marginTop: 20, marginBottom: 6, display: "flex", alignItems: "center" }}>
            <span style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: "0.09em", color: "#8A938C" }}>SAVED VIEWS</span>
            <span style={{
              marginLeft: "auto", width: 20, height: 20, borderRadius: 5, border: "1px solid #E4E7E3",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, color: "#8A938C",
            }}>+</span>
          </div>
          {[["Healthcare, lighting open", "12"], ["Discovered, no spec yet", "8"],
            ["Rival named, still or-equal", "6"], ["Bid opens in 30 days", "9"]].map(([v, n]) => (
            <div key={v} style={{
              height: 30, display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "0 10px", fontSize: 12.5, color: "#4B554E",
            }}>
              <span>{v}</span>
              <span style={{ fontFamily: MONO, fontSize: 11, color: "#9AA39D" }}>{n}</span>
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

        {/* main */}
        <main style={{ maxWidth: 1180, margin: "0 auto", padding: "0 30px 60px", width: "100%" }}>
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

          {/* Disclosure, not apology. Gemini's read was that a paragraph of
              caveat in the page body sounds defensive to an investor who
              already assumes a demo contains sample data. Same information,
              stated as a product affordance and hoverable for the detail. */}
          <div
            title="Maine State Prison is a live record from the corpus. The other projects, notes, brand mentions and freshness bars are illustrative, shown at the coverage we are building toward."
            style={{
              display: "inline-flex", gap: 7, alignItems: "center", background: "#fff",
              border: "1px solid #E4E7E3", borderRadius: 999, padding: "5px 12px", marginBottom: 18,
              cursor: "default",
            }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: "#C0631A" }} />
            <span style={{ fontFamily: MONO, fontSize: 10, letterSpacing: "0.07em", color: "#A2601C" }}>DEMO DATA</span>
            <span style={{ fontSize: 12, color: "#8A938C" }}>1 live record, 3 illustrative</span>
          </div>

          <div style={{ fontFamily: MONO, fontSize: 10.5, letterSpacing: "0.09em", color: "#16643A", marginBottom: 8 }}>
            SATURDAY, AUGUST 8
          </div>
          <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-0.03em", margin: "0 0 8px" }}>
            Good morning, Asif.
          </h1>
          <p style={{ fontSize: 14, color: "#5B655E", maxWidth: 580, margin: "0 0 26px" }}>
            Three things changed on projects you track, and four in Maine are early enough to still
            influence. Not a browse-everything list.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 320px", gap: 24, alignItems: "start" }}>
            {/* left */}
            <div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 10 }}>
                <h2 style={{ fontSize: 16, fontWeight: 700, letterSpacing: "-0.02em", margin: 0 }}>
                  Changed on your tracked projects
                </h2>
                <span style={{ fontSize: 12.5, color: "#16643A", cursor: "pointer" }}>View pipeline</span>
              </div>

              <div style={{ ...card, marginBottom: 26 }}>
                {SEED_CHANGES.map((c, i) => {
                  const t = TAG_TONE[c.tone];
                  return (
                    <div key={c.headline} style={{
                      display: "flex", gap: 12, padding: "13px 16px", alignItems: "flex-start",
                      borderTop: i === 0 ? "none" : "1px solid #F2F4F1",
                    }}>
                      <span style={{
                        fontFamily: MONO, fontSize: 10, background: t.bg, color: t.fg,
                        padding: "2px 7px", borderRadius: 5, marginTop: 1,
                      }}>{c.tag}</span>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontSize: 14, fontWeight: 600 }}>{c.headline}</div>
                        <div style={{ fontSize: 12.5, color: "#7A857E", marginTop: 2 }}>{c.project}</div>
                      </div>
                      <span style={{ fontFamily: MONO, fontSize: 11, color: "#9AA39D", whiteSpace: "nowrap" }}>{c.when}</span>
                    </div>
                  );
                })}
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                <h2 style={{ fontSize: 16, fontWeight: 700, letterSpacing: "-0.02em", margin: 0 }}>
                  New in Maine, spec still open
                </h2>
                <div style={{ marginLeft: "auto", display: "flex", background: "#EBEEE9", borderRadius: 8, padding: 3, gap: 2 }}>
                  {[["open", "Spec still open"], ["soon", "Bid opens soon"], ["rival", "Rival named"]].map(([k, l]) => (
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
                  const s = scoreStyle(p.score);
                  const isTracked = !!tracked[p.id];
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
                          {p.score == null ? "EARLY" : "SCORE"}
                        </div>
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <a href={p.real ? `/preview/logged-in/` : undefined} style={{
                          fontSize: 15, fontWeight: 700, color: "#111512", textDecoration: "none", display: "block",
                        }}>{p.name}</a>
                        <div style={{ fontSize: 12.5, color: "#6B756E", marginTop: 3 }}>
                          {[p.city && `${p.city}, ${p.state}`, p.owner].filter(Boolean).join(" · ")}
                          {p.docCount > 0 ? ` · ${p.docCount} documents parsed` : " · no documents held yet"}
                        </div>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                          {p.divisions.length > 0 ? p.divisions.map((d) => (
                            <span key={d.code} style={{
                              fontFamily: MONO, fontSize: 11, background: "#F2F4F1", borderRadius: 5, padding: "3px 7px", color: "#4B554E",
                            }}>{d.code} {d.label}</span>
                          )) : (
                            <span style={{
                              fontFamily: MONO, fontSize: 11, background: "#F2F4F1", borderRadius: 5,
                              padding: "3px 7px", color: "#8A938C",
                            }}>Scope not read yet</span>
                          )}
                        </div>
                        <div style={{ fontSize: 12.5, color: "#8A938C", marginTop: 8 }}>{p.source}</div>
                      </div>

                      <div style={{ width: 128, flexShrink: 0, textAlign: "right" }}>
                        <div style={{ fontSize: 12.5, color: p.urgent ? "#A2601C" : "#7A857E" }}>{p.urgency}</div>
                        <div style={{ fontFamily: MONO, fontSize: 13, marginTop: 4, color: p.value ? "#111512" : "#9AA39D" }}>
                          {p.value ?? "Not pulled"}
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
                Showing {rows.length} of 26 matches. Scored on how much of the spec is still winnable,
                not on how new the project is.
              </p>
            </div>

            {/* right rail */}
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ ...card, border: "1px solid #C6DDCF", padding: 16 }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 12 }}>
                  <span style={railTitle}>Your notes</span>
                  <span style={{ fontFamily: MONO, fontSize: 11, color: "#8A938C" }}>{SEED_NOTES.length}</span>
                </div>
                {SEED_NOTES.map((n) => (
                  <div key={n.id} style={{ marginBottom: 14 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span style={{
                        fontFamily: MONO, fontSize: 9.5, background: "#F0F2EF", color: "#5B655E",
                        padding: "2px 6px", borderRadius: 5,
                      }}>{n.kind}</span>
                      <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 10.5, color: "#9AA39D" }}>{n.when}</span>
                    </div>
                    <p style={{ fontSize: 12.5, color: "#4B554E", lineHeight: 1.55, margin: "0 0 4px" }}>{n.text}</p>
                    <div style={{ fontSize: 11.5, color: "#8A938C" }}>{n.project}</div>
                  </div>
                ))}
                <div style={{ fontSize: 11.5, color: "#8A938C", borderTop: "1px solid #F2F4F1", paddingTop: 10 }}>
                  What you know about a job lives here, not in a CRM nobody opens.
                </div>
              </div>

              <div style={{ ...card, padding: 16 }}>
                <div style={{ ...railTitle, marginBottom: 10 }}>Your pipeline</div>
                {SEED_STAGES.map((s) => (
                  <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 9, padding: "6px 0" }}>
                    <span style={{ width: 7, height: 7, borderRadius: 999, background: s.dot }} />
                    <span style={{ fontSize: 12.5 }}>{s.label}</span>
                    <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 11.5, color: "#5B655E" }}>{s.count}</span>
                  </div>
                ))}
                <div style={{ fontSize: 11.5, color: "#8A938C", borderTop: "1px solid #F2F4F1", paddingTop: 10, marginTop: 8 }}>
                  Cards move when you say so, not when a crawler guesses.
                </div>
              </div>

              <div style={{ ...card, padding: 16 }}>
                <div style={{ ...railTitle }}>Brand mentions</div>
                <div style={{ fontSize: 11.5, color: "#8A938C", marginBottom: 10 }}>Where your brand or a rival got named.</div>
                {SEED_MENTIONS.map((m, i) => (
                  <div key={i} style={{ marginBottom: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                      <span style={{ width: 7, height: 7, borderRadius: 999, background: m.rival ? "#C0631A" : "#16643A" }} />
                      <span style={{ fontSize: 13, fontWeight: 600 }}>{m.brand}</span>
                      <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 10.5, color: "#9AA39D" }}>{m.when}</span>
                    </div>
                    <p style={{ fontSize: 12, color: "#5B655E", margin: "3px 0 0", lineHeight: 1.5 }}>{m.text}</p>
                  </div>
                ))}
              </div>

              <div style={{ ...card, padding: 16 }}>
                <div style={{ ...railTitle, marginBottom: 12 }}>Data freshness</div>
                {SEED_FRESHNESS.map((f) => (
                  <div key={f.label} style={{ marginBottom: 12 }}>
                    <div style={{ display: "flex", alignItems: "baseline" }}>
                      <span style={{ fontSize: 12.5 }}>{f.label}</span>
                      <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 10.5, color: "#9AA39D" }}>{f.when}</span>
                    </div>
                    <div style={{ height: 3, background: "#EDF0EC", borderRadius: 999, marginTop: 6 }}>
                      <div style={{
                        width: `${f.pct}%`, height: "100%", borderRadius: 999,
                        background: f.stale ? "#C0631A" : "#16643A",
                      }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
