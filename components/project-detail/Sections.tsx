import type { EnrichmentFact, Project, SpecCitation } from "@/lib/types";
import { citationPosition, displaySource, type DerivedScope } from "./helpers";

export function AbsentFact({ label, reason, signal }: { label: string; reason: string; signal?: string }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3">
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">{label}</dt>
      <dd className="mt-1 text-sm font-medium text-[var(--color-gray-600)]">{reason}</dd>
      {signal && <p className="mt-1.5 text-[11px] leading-snug text-[var(--color-green)]">{signal}</p>}
    </div>
  );
}

// The facts grid's rules come from each cell's own box-shadow, not a
// container background showing through a 1px gap, and the grid is
// flex-wrap rather than CSS grid -- see the container comment in
// ProjectDetailView.tsx for why (a variable fact count leaves the last
// row incomplete, and grid reserves that unfilled space as real, borderable
// area). flexBasis mirrors the old minmax(165px, 1fr) sizing.
const FACT_CELL_STYLE = {
  background: "#fff",
  padding: "14px 16px",
  boxShadow: "1px 0 0 var(--sx-line), 0 1px 0 var(--sx-line)",
  flex: "1 1 165px",
  minWidth: 165,
} as const;

// "Never render an empty field. Omit the card." Grid reflows to however
// many real facts exist.
export function Fact({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  if (!value) return null;
  return (
    <div style={FACT_CELL_STYLE}>
      <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 1.3, textTransform: "uppercase", color: "var(--sx-muted)", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 14.5, fontWeight: 600, fontFamily: mono ? "var(--font-mono)" : undefined }}>{value}</div>
    </div>
  );
}

export function AbsentFactCell({ label, reason }: { label: string; reason: string }) {
  return (
    <div style={FACT_CELL_STYLE}>
      <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 1.3, textTransform: "uppercase", color: "var(--sx-muted)", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 13.5, color: "var(--sx-faint)" }}>{reason}</div>
    </div>
  );
}

// SCOPE TAB. Divisions naming nobody sort first -- the entire reason a
// mechanical or electrical rep would care about a record like this, and
// invisible if buried at the bottom.
export function ScopeTab({
  csiScope,
  citations,
  derivedScope,
}: {
  csiScope: EnrichmentFact[] | undefined;
  citations: SpecCitation[];
  derivedScope: DerivedScope[];
}) {
  const citedDivisions = new Set(citations.map((c) => c.csi_division).filter(Boolean));
  const hasScope = (csiScope?.length ?? 0) > 0 || derivedScope.length > 0;

  if (!hasScope) {
    return (
      <div style={{ border: "1px dashed var(--sx-dashed)", background: "var(--sx-page-bg)", borderRadius: 12, padding: 24 }}>
        <p style={{ fontWeight: 700, marginBottom: 6 }}>Scope has not been read from a specification yet</p>
        <p style={{ fontSize: 13.5, color: "var(--sx-muted)", lineHeight: 1.6 }}>
          This is a discovered project. No division-by-division breakdown exists until a specification document is
          published and read.
        </p>
      </div>
    );
  }

  const rows = [...(csiScope ?? [])].sort((a, b) => {
    const aCited = citedDivisions.has(a.field_key) ? 1 : 0;
    const bCited = citedDivisions.has(b.field_key) ? 1 : 0;
    return aCited - bCited;
  });

  return (
    <div>
      {derivedScope.length > 0 && (
        <div style={{ border: "1px solid var(--sx-line)", background: "var(--sx-page-bg)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
          <p style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 1.3, textTransform: "uppercase", color: "var(--sx-muted)", marginBottom: 8 }}>
            Trades this scope requires
          </p>
          <ul style={{ display: "flex", flexDirection: "column", gap: 6, listStyle: "none", padding: 0, margin: 0 }}>
            {derivedScope.map((s) => (
              <li key={s.division} style={{ fontSize: 13.5 }}>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--sx-green)" }}>Div {s.division}</span>{" "}
                <span style={{ fontWeight: 600 }}>{s.label}</span>{" "}
                <span style={{ color: "var(--sx-muted)" }}>({s.because})</span>
              </li>
            ))}
          </ul>
          <p style={{ marginTop: 10, fontSize: 12, lineHeight: 1.5, color: "var(--sx-muted)" }}>
            Requirements implied by the declared scope, not products selected on this project. No manufacturer can be
            named without a specification document.
          </p>
        </div>
      )}

      {rows.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 12 }}>
          {rows.map((fact) => {
            const namesNobody = !citedDivisions.has(fact.field_key);
            return (
              <div
                key={fact.field_key}
                style={{
                  border: `1px solid ${namesNobody ? "var(--sx-green)" : "var(--sx-line)"}`,
                  background: namesNobody ? "var(--sx-panel)" : "#fff",
                  borderRadius: 12,
                  padding: 16,
                }}
              >
                <span
                  style={{
                    fontSize: 10.5,
                    fontWeight: 700,
                    letterSpacing: 1,
                    textTransform: "uppercase",
                    color: namesNobody ? "var(--sx-forest)" : "var(--sx-muted)",
                    background: namesNobody ? "var(--sx-chip)" : "var(--sx-page-bg)",
                    padding: "2px 8px",
                    borderRadius: 999,
                  }}
                >
                  {namesNobody ? "Names nobody" : "Cited"}
                </span>
                <p style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 15.5, margin: "10px 0 4px" }}>{fact.label}</p>
                <p style={{ fontSize: 13, color: "var(--sx-muted)", lineHeight: 1.5 }}>{fact.value}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

const POSITION_LEGEND = [
  { label: "Open to equals", tone: "green", meaning: "Section names alternates and says \"or approved equal\" outright" },
  { label: "Acceptable manufacturer", tone: "green", meaning: "One of several on a named list, list explicitly not closed" },
  { label: "Basis of design", tone: "grey", meaning: "Product the section was drawn around" },
  { label: "Named", tone: "grey", meaning: "Manufacturer appears in the section" },
  { label: "Approved vendor", tone: "grey", meaning: "A source to buy through, not the manufacturer of record" },
  { label: "Fabricator", tone: "amber", meaning: "Named to fabricate the assembly, hardest to displace" },
] as const;

const TONE_STYLE: Record<string, { bg: string; color: string }> = {
  green: { bg: "var(--sx-chip)", color: "var(--sx-forest)" },
  grey: { bg: "var(--sx-page-bg)", color: "var(--sx-muted)" },
  amber: { bg: "var(--sx-amber-tint)", color: "#7c4a03" },
};

export function SpecificationTab({
  citations,
  governingRule,
  documentCount,
  hasTeam,
  hasScope,
}: {
  citations: SpecCitation[];
  governingRule?: { text: string; cite: string } | null;
  documentCount: number;
  hasTeam: boolean;
  hasScope: boolean;
}) {
  if (citations.length === 0) {
    return (
      <div style={{ border: "1px dashed var(--sx-dashed)", background: "var(--sx-page-bg)", borderRadius: 12, padding: 24 }}>
        <p style={{ fontWeight: 700, marginBottom: 6 }}>No specification document has been published for this project</p>
        <p style={{ fontSize: 13.5, color: "var(--sx-muted)", lineHeight: 1.6, maxWidth: "60ch" }}>
          This is a discovered project rather than a bid record. A manufacturer cannot be named without a document
          behind it{documentCount > 0 ? ` (${documentCount} document${documentCount === 1 ? "" : "s"} held, none is a specification)` : ""}.
        </p>
        <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.3, textTransform: "uppercase", color: "var(--sx-muted)", margin: "18px 0 8px" }}>
          What you can act on today
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
          {hasTeam && (
            <div style={{ background: "#fff", border: "1px solid var(--sx-line)", borderRadius: 9, padding: 12, fontSize: 13 }}>
              The construction team is known. See the Team tab.
            </div>
          )}
          {hasScope && (
            <div style={{ background: "#fff", border: "1px solid var(--sx-line)", borderRadius: 9, padding: 12, fontSize: 13 }}>
              The declared scope is known. See the Scope tab.
            </div>
          )}
          <div style={{ background: "#fff", border: "1px solid var(--sx-line)", borderRadius: 9, padding: 12, fontSize: 13 }}>
            Track this project to be alerted if a spec publishes.
          </div>
        </div>
      </div>
    );
  }

  const byDivision = new Map<string, SpecCitation[]>();
  for (const c of citations) {
    const k = c.csi_division || "—";
    byDivision.set(k, [...(byDivision.get(k) ?? []), c]);
  }

  return (
    <div>
      {governingRule && (
        <div style={{ background: "var(--sx-panel)", border: "1px solid var(--sx-green)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
          <p style={{ fontSize: 13.5, lineHeight: 1.6 }}>
            <strong>{governingRule.cite}:</strong> &ldquo;{governingRule.text}&rdquo; Every named product on this project is
            substitutable unless otherwise stated.
          </p>
        </div>
      )}

      <details style={{ marginBottom: 16, border: "1px solid var(--sx-line)", borderRadius: 12, padding: "10px 16px" }}>
        <summary style={{ cursor: "pointer", fontSize: 13, fontWeight: 600, color: "var(--sx-muted)" }}>How to read a position</summary>
        <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
          {POSITION_LEGEND.map((row) => (
            <div key={row.label} style={{ fontSize: 12.5, display: "flex", gap: 8, alignItems: "baseline" }}>
              <span style={{ ...TONE_STYLE[row.tone], padding: "1px 8px", borderRadius: 999, fontSize: 10.5, fontWeight: 700, whiteSpace: "nowrap" }}>
                {row.label}
              </span>
              <span style={{ color: "var(--sx-muted)" }}>{row.meaning}</span>
            </div>
          ))}
        </div>
      </details>

      {[...byDivision.entries()].map(([div, rows]) => {
        const trade = rows[0]?.csi_section || `Division ${div}`;
        return (
          <div key={div} style={{ marginBottom: 18 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
              <span style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 15.5 }}>{trade}</span>
              {div !== "—" && <span style={{ fontSize: 12, color: "var(--sx-muted)" }}>CSI Division {div}</span>}
            </div>
            {rows.map((c, i) => {
              const pos = citationPosition(c);
              return (
                <div key={i} style={{ padding: "17px 0", borderTop: "1px solid var(--sx-line)" }}>
                  <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 16, fontWeight: 600 }}>{c.manufacturer}</span>
                    {pos && (
                      <span style={{ ...TONE_STYLE[pos.tone], padding: "2px 9px", borderRadius: 999, fontSize: 10.5, fontWeight: 700, whiteSpace: "nowrap" }} title={pos.hint}>
                        {pos.label}
                      </span>
                    )}
                  </div>
                  {c.product && <div style={{ fontSize: 14, marginTop: 2 }}>{c.product}</div>}
                  {c.quoted_text?.trim() && (
                    <blockquote style={{ borderLeft: "2px solid var(--sx-green)", padding: "4px 0 4px 12px", margin: "8px 0 0", fontStyle: "italic", fontSize: 13 }}>
                      &ldquo;{c.quoted_text}&rdquo;
                    </blockquote>
                  )}
                  <div style={{ marginTop: 6, fontSize: 12, color: "var(--sx-muted)" }}>
                    Div {div} · CSI {c.csi_section ?? "—"}
                    <span style={{ float: "right", fontFamily: "var(--font-mono)" }}>
                      page {c.page_number}
                      {c.source_url && (
                        <>
                          {" · "}
                          <a href={c.source_url} target="_blank" rel="noopener noreferrer">
                            open the source document
                          </a>
                        </>
                      )}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}

      <p style={{ marginTop: 12, fontSize: 11.5, color: "var(--sx-muted)" }}>
        Quoted from documents we hold. Being named is not an award, a specification can name a product and the job
        be built with another.
      </p>
    </div>
  );
}

export function TeamTab({ team }: { team: EnrichmentFact[] | undefined; contacts: EnrichmentFact[] | undefined }) {
  const rows = team ?? [];
  if (rows.length === 0) {
    return (
      <div style={{ border: "1px dashed var(--sx-dashed)", background: "var(--sx-page-bg)", borderRadius: 12, padding: 24, fontSize: 13.5, color: "var(--sx-muted)" }}>
        No construction team has been identified for this project yet.
      </div>
    );
  }
  const specAuthorKey = rows.find((r) => /architect|engineer of record/i.test(r.label))?.field_key;
  return (
    <div style={{ background: "#fff", border: "1px solid var(--sx-line)", borderRadius: 12, overflow: "hidden" }}>
      {rows.map((fact) => (
        <div key={fact.field_key} style={{ display: "flex", flexWrap: "wrap", gap: 10, padding: "14px 18px", borderTop: "1px solid var(--sx-line)" }}>
          <div style={{ flex: "0 0 190px", fontSize: 11.5, fontWeight: 700, textTransform: "uppercase", color: "var(--sx-muted)" }}>{fact.label}</div>
          <div style={{ flex: 1, fontSize: 14 }}>{fact.value || <span style={{ color: "var(--sx-muted)" }}>Not announced</span>}</div>
          {fact.field_key === specAuthorKey && (
            <span style={{ background: "var(--sx-chip)", color: "var(--sx-forest)", padding: "2px 9px", borderRadius: 999, fontSize: 10.5, fontWeight: 700 }}>
              Spec author
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

export function DocumentsTab({ documents }: { documents: Project["documents"] }) {
  if (!documents || documents.length === 0) {
    return (
      <div style={{ border: "1px dashed var(--sx-dashed)", background: "var(--sx-page-bg)", borderRadius: 12, padding: 24 }}>
        <p style={{ fontWeight: 700, marginBottom: 6 }}>No documents held for this project</p>
        <p style={{ fontSize: 13.5, color: "var(--sx-muted)", lineHeight: 1.6, maxWidth: "60ch" }}>
          This record came from search-grounded discovery rather than a bid portal. See the activity feed for the
          sources behind it.
        </p>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {documents.map((doc) => (
        <a
          key={doc.url}
          href={doc.url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ border: "1px solid var(--sx-line)", borderRadius: 9, padding: "14px 16px", display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center" }}
        >
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>{doc.title}</div>
            <div style={{ fontSize: 12, color: "var(--sx-muted)" }}>{doc.document_type}</div>
          </div>
          <span style={{ fontSize: 13, color: "var(--sx-forest)", whiteSpace: "nowrap" }}>Open document →</span>
        </a>
      ))}
    </div>
  );
}

export function BriefTab({ project }: { project: Project }) {
  const brief = project.enrichment?.executive_brief[0];
  if (!brief) {
    return (
      <div>
        <p style={{ fontSize: 16, lineHeight: 1.7, maxWidth: "76ch" }}>{project.description}</p>
        {project.key_specs.length > 0 && (
          <ul style={{ marginTop: 16, paddingLeft: 20, display: "flex", flexDirection: "column", gap: 8, fontSize: 14, color: "var(--sx-muted)" }}>
            {project.key_specs.map((spec) => (
              <li key={spec}>{spec}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }
  return (
    <div>
      <p style={{ fontSize: 16, lineHeight: 1.7, maxWidth: "76ch" }}>{brief.value}</p>
      {brief.sources && (
        <div style={{ marginTop: 14, paddingTop: 10, borderTop: "1px solid var(--sx-line)", fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--sx-muted)" }}>
          {displaySource(brief.sources)}
        </div>
      )}
    </div>
  );
}
