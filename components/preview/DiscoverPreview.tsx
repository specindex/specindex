"use client";

import { useMemo, useState } from "react";
import type { Project } from "@/lib/types";
import { formatUsd, toDisplayCase } from "@/lib/format";

// Discover (screen 2 of the handoff): everything the licence covers, in one
// place. Rendered against the real Maine territory.
//
// Local state only -- tracking and selection live in useState so the
// interaction can be judged before the notes/tracking schema is committed to.

// Score rule from the handoff, verbatim: >=70 green, 60-69 amber, <60 grey,
// null grey rendered "--". A null must never render as 0.
function scoreStyle(total: number | null | undefined) {
  if (total == null) return { bg: "#F0F2EF", fg: "#9AA39D", label: "--" };
  if (total >= 70) return { bg: "#E7EFE9", fg: "#16643A", label: String(total) };
  if (total >= 60) return { bg: "#FBF2E6", fg: "#C0631A", label: String(total) };
  return { bg: "#F0F2EF", fg: "#5B655E", label: String(total) };
}

const FILTERS = [
  { key: "all", label: "All" },
  { key: "open", label: "Spec still open" },
  { key: "nospec", label: "Discovered, no spec" },
] as const;

export function DiscoverPreview({ projects, total }: { projects: Project[]; total: number }) {
  const [filter, setFilter] = useState<string>("all");
  const [tracked, setTracked] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState<Record<string, boolean>>({});

  const rows = useMemo(() => {
    if (filter === "open") {
      // "Spec still open" means the window to influence has not shut: the job
      // is not yet under construction. Deliberately NOT "has documents" --
      // that would hide the 97% of the corpus this territory is mostly made
      // of, which is exactly the population a rep wants to reach early.
      return projects.filter((p) => !["under_construction", "completed"].includes(String(p.status)));
    }
    if (filter === "nospec") {
      return projects.filter((p) => (p.document_count ?? 0) === 0);
    }
    return projects;
  }, [projects, filter]);

  const selectedCount = Object.values(selected).filter(Boolean).length;

  function trackAllSelected() {
    const next = { ...tracked };
    for (const id of Object.keys(selected)) if (selected[id]) next[id] = true;
    setTracked(next);
    setSelected({});
  }

  const mono = "var(--font-mono)";

  return (
    <div style={{ fontFamily: "var(--font-sans)", background: "#F5F6F4", minHeight: "100vh", color: "#111512" }}>
      <div style={{ display: "grid", gridTemplateColumns: "232px minmax(0,1fr)", alignItems: "start" }}>
        {/* sidebar */}
        <aside style={{
          position: "sticky", top: 0, height: "100vh", background: "#FBFCFB",
          borderRight: "1px solid #E4E7E3", display: "flex", flexDirection: "column", padding: "17px 16px 13px",
        }}>
          <div style={{ fontSize: 16, letterSpacing: "-0.02em", marginBottom: 18 }}>
            <span style={{ fontWeight: 800 }}>Spec</span><span style={{ fontWeight: 600, color: "#3D4A42" }}>Index</span>
          </div>
          <div style={{
            width: "100%", background: "#fff", border: "1px solid #E4E7E3", borderRadius: 9,
            padding: "8px 10px", marginBottom: 16,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span style={{ width: 7, height: 7, borderRadius: 999, background: "#16643A" }} />
              <span style={{ fontFamily: mono, fontSize: 9.5, letterSpacing: "0.08em", color: "#8A938C" }}>TERRITORY</span>
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, marginTop: 2 }}>Maine</div>
          </div>
          {[["Today", "7"], ["Pipeline", String(Object.values(tracked).filter(Boolean).length)], ["Discover", String(total)]].map(([label, n]) => (
            <div key={label} style={{
              height: 33, display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "0 10px", borderRadius: 8, fontSize: 13.5,
              background: label === "Discover" ? "#E7EFE9" : "transparent",
              color: label === "Discover" ? "#0E4227" : "#3D4A42",
              fontWeight: label === "Discover" ? 600 : 500,
            }}>
              <span>{label}</span>
              <span style={{ fontFamily: mono, fontSize: 11, color: label === "Discover" ? "#16643A" : "#9AA39D" }}>{n}</span>
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
        <main style={{ maxWidth: 1180, padding: "0 34px 60px", width: "100%" }}>
          <div style={{
            position: "sticky", top: 0, zIndex: 5, height: 56, display: "flex", alignItems: "center", gap: 16,
            background: "rgba(245,246,244,0.94)", backdropFilter: "blur(8px)",
            borderBottom: "1px solid #E4E7E3", marginBottom: 22,
          }}>
            <span style={{ fontSize: 15, fontWeight: 700 }}>Discover</span>
            <span style={{
              marginLeft: "auto", height: 31, display: "flex", alignItems: "center", padding: "0 14px",
              borderRadius: 999, background: "#EFF6F1", border: "1px solid #C6DDCF", color: "#16643A",
              fontWeight: 600, fontSize: 13,
            }}>Pipeline · {Object.values(tracked).filter(Boolean).length}</span>
          </div>

          <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-0.03em", margin: "0 0 6px" }}>
            Everything in Maine
          </h1>
          <p style={{ fontSize: 14, color: "#5B655E", margin: "0 0 20px" }}>
            {total} commercial projects your licence covers. Sorted by priority score.
          </p>

          {/* filters */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
            <div style={{ display: "flex", background: "#EBEEE9", borderRadius: 8, padding: 3, gap: 2 }}>
              {FILTERS.map((f) => (
                <button key={f.key} onClick={() => setFilter(f.key)} style={{
                  border: "none", cursor: "pointer", borderRadius: 6, padding: "6px 12px", fontSize: 13,
                  fontFamily: "var(--font-sans)",
                  background: filter === f.key ? "#fff" : "transparent",
                  boxShadow: filter === f.key ? "0 1px 2px rgba(17,21,18,0.09)" : "none",
                  fontWeight: filter === f.key ? 600 : 400,
                  color: filter === f.key ? "#111512" : "#5B655E",
                }}>
                  {f.label}
                  <span style={{ fontFamily: mono, fontSize: 11, color: "#8A938C", marginLeft: 6 }}>
                    {f.key === "all" ? projects.length
                      : f.key === "open" ? projects.filter((p) => !["under_construction","completed"].includes(String(p.status))).length
                      : projects.filter((p) => (p.document_count ?? 0) === 0).length}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* bulk-selection bar */}
          {selectedCount > 0 && (
            <div style={{
              display: "flex", alignItems: "center", gap: 12, background: "#fff",
              border: "1px solid #16643A", borderRadius: 9, padding: "10px 14px", marginBottom: 10,
            }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>{selectedCount} selected</span>
              <button onClick={() => setSelected({})} style={{
                background: "none", border: "none", color: "#5B655E", fontSize: 12.5, cursor: "pointer",
                fontFamily: "var(--font-sans)",
              }}>Clear</button>
              <button onClick={trackAllSelected} style={{
                marginLeft: "auto", background: "#16643A", color: "#fff", border: "none", borderRadius: 8,
                padding: "7px 14px", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "var(--font-sans)",
              }}>Track {selectedCount} project{selectedCount === 1 ? "" : "s"}</button>
            </div>
          )}

          {/* table */}
          <div style={{ background: "#fff", border: "1px solid #E4E7E3", borderRadius: 12, overflow: "hidden" }}>
            <div style={{
              display: "grid", gridTemplateColumns: "17px 40px minmax(0,1fr) 130px 96px 92px",
              gap: 14, padding: "10px 16px", background: "#F7F8F6", borderBottom: "1px solid #E4E7E3",
              fontFamily: mono, fontSize: 10, letterSpacing: "0.07em", color: "#8A938C",
            }}>
              <span /><span>SCORE</span><span>PROJECT</span><span>STAGE</span>
              <span style={{ textAlign: "right" }}>VALUE</span><span />
            </div>

            {rows.map((p) => {
              const s = scoreStyle(p.score?.total);
              const isTracked = !!tracked[p.id];
              return (
                <div key={p.id} style={{
                  display: "grid", gridTemplateColumns: "17px 40px minmax(0,1fr) 130px 96px 92px",
                  gap: 14, padding: "12px 16px", borderBottom: "1px solid #F2F4F1", alignItems: "center",
                }}>
                  <input type="checkbox" checked={!!selected[p.id]}
                    onChange={(e) => setSelected({ ...selected, [p.id]: e.target.checked })}
                    style={{ width: 15, height: 15, accentColor: "#16643A", cursor: "pointer" }} />

                  <span style={{
                    fontFamily: mono, fontSize: 12.5, textAlign: "center", background: s.bg, color: s.fg,
                    borderRadius: 5, padding: "3px 0",
                  }}>{s.label}</span>

                  <div style={{ minWidth: 0 }}>
                    <a href={`/project/${p.id}/`} style={{
                      fontSize: 13.5, fontWeight: 600, color: "#111512", textDecoration: "none",
                      display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>{toDisplayCase(p.name)}</a>
                    <div style={{ fontSize: 12, color: "#8A938C", marginTop: 2 }}>
                      {[toDisplayCase(p.city || ""), p.county ? `${toDisplayCase(p.county)} County` : ""].filter(Boolean).join(" · ")}
                      {(p.document_count ?? 0) > 0 ? ` · ${p.document_count} doc${p.document_count === 1 ? "" : "s"}` : ""}
                    </div>
                  </div>

                  <span style={{
                    fontFamily: mono, fontSize: 10, letterSpacing: "0.06em", justifySelf: "start",
                    padding: "3px 8px", borderRadius: 999,
                    background: String(p.status) === "bidding" ? "#FBF2E6" : "#F0F2EF",
                    color: String(p.status) === "bidding" ? "#A2601C" : "#5B655E",
                  }}>{String(p.status).toUpperCase().replace(/_/g, " ")}</span>

                  <span style={{ fontFamily: mono, fontSize: 12.5, textAlign: "right", color: "#4B554E" }}>
                    {p.estimated_value_usd != null ? formatUsd(p.estimated_value_usd) : "--"}
                  </span>

                  <button onClick={() => setTracked({ ...tracked, [p.id]: !isTracked })} style={{
                    height: 27, borderRadius: 7, fontSize: 12, fontWeight: 600, cursor: "pointer",
                    fontFamily: "var(--font-sans)",
                    background: isTracked ? "#EFF6F1" : "#16643A",
                    color: isTracked ? "#16643A" : "#fff",
                    border: isTracked ? "1px solid #C6DDCF" : "none",
                  }}>{isTracked ? "Tracking" : "Track"}</button>
                </div>
              );
            })}

            <div style={{ padding: "12px 16px", fontSize: 12.5, color: "#8A938C" }}>
              Showing {rows.length} of {total}. Production loads the rest on scroll.
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
