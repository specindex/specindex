import Link from "next/link";
import { StatusPill } from "@/components/StatusPill";
import { formatDate, formatSf, formatUsd, toDisplayCase, typeLabel } from "@/lib/format";
import type { Project } from "@/lib/types";
import {
  ActivityFeed,
  FIREBASE_AUTH_ENABLED,
  GatedBanner,
  PipelineBox,
  ProjectAskPanel,
  ScoreCard,
  TabBar,
  TriageNav,
} from "@/components/project-detail/ClientBits";
import { EMPTY_FACT_VALUES, buildFeedItems, deriveScope, findTeamFact, locationLine } from "@/components/project-detail/helpers";
import {
  AbsentFactCell,
  BriefTab,
  DocumentsTab,
  Fact,
  ScopeTab,
  SpecificationTab,
  TeamTab,
} from "@/components/project-detail/Sections";

// Shared render for a single project's detail record -- used by both the
// statically-generated pages (app/projects/[id]/page.tsx, top ~200 by score,
// real SEO/JSON-LD) and the client-rendered fallback (app/projects/view/page.tsx)
// that serves every other project at any scale. Server-rendered: everything
// except tracking, the ask panel, the score breakdown popover, prev/next nav
// and the tab switcher itself lives in the initial HTML, so a crawler or
// curl sees the full record, not an empty shell.
//
// One template renders both a "deep" record (documents + citations) and a
// "shallow" one (zero documents) -- every section below has a written empty
// state for the shallow case rather than a blank card.
export function ProjectDetailView({ project }: { project: Project }) {
  const documentCount = project.document_count ?? 0;
  const citations = project.spec_citations ?? [];
  const derivedScope = deriveScope(project.description ?? "", project.competitor_watch ?? []);
  const gcFact = !project.general_contractor ? findTeamFact(project, "general_contractor") : undefined;
  const architectFact = !project.architect ? findTeamFact(project, "architect") : undefined;
  const feedItems = buildFeedItems(project);
  const hasDocuments = documentCount > 0 && citations.length > 0;

  // The "read" panel inverts styling by record depth: a record with nothing
  // cited does not get the dark hero treatment, or every record looks
  // equally authoritative and none of them are trusted.
  const readHeadline = hasDocuments
    ? `${citations.length} manufacturer${citations.length === 1 ? "" : "s"} named across this project's own specification documents.`
    : `A discovered project. No specification document has been read yet, so no manufacturer can be named.`;
  const readStats: { num: string; text: string }[] = hasDocuments
    ? [
        { num: String(citations.length), text: "manufacturers cited" },
        { num: String(documentCount), text: `document${documentCount === 1 ? "" : "s"} held` },
        { num: String(derivedScope.length + (project.enrichment?.csi_scope.length ?? 0)), text: "divisions in scope" },
      ]
    : [
        { num: project.general_contractor || gcFact?.value ? "1" : "0", text: "general contractor known" },
        { num: String(derivedScope.length), text: "trades implied by scope" },
        { num: String(project.mentioned_brands.length), text: "brands mentioned" },
      ];
  // A row of three "0" stat tiles right above the facts grid below (which
  // already states the same absences in "Unassigned, pre-award" style text)
  // repeats one piece of information twice in two different visual systems
  // within ~150px of each other. When there's genuinely nothing to point to,
  // skip the tiles entirely rather than give zero weight the same prominent
  // elevated-card treatment as a real number.
  const readStatsAllZero = readStats.every((s) => s.num === "0");

  const facts: { label: string; value: string; mono?: boolean }[] = [
    { label: "Estimated value", value: formatUsd(project.estimated_value_usd) },
    { label: "Opened / announced", value: formatDate(project.opened_or_announced_date), mono: true },
  ].filter((f) => f.value && !EMPTY_FACT_VALUES.has(f.value));

  const teamCount = project.enrichment?.team.length ?? 0;
  const tabCounts = {
    brief: 1,
    scope: derivedScope.length + (project.enrichment?.csi_scope.length ?? 0),
    spec: citations.length,
    team: teamCount,
    documents: project.documents?.length ?? 0,
  };

  return (
    <article style={{ background: "var(--sx-page-bg)" }}>
      <div style={{ maxWidth: 1320, margin: "0 auto", padding: "20px 32px 80px" }}>
        {/* Grounding strip */}
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "12px 20px", marginBottom: 16 }}>
          <Link href="/projects/" style={{ fontSize: 13.5, color: "var(--sx-muted)" }}>
            ← All projects
          </Link>
          {FIREBASE_AUTH_ENABLED && <TriageNav projectId={project.id} />}
          {project.enrichment?.checked_at && (
            <div style={{ marginLeft: "auto", display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, fontFamily: "var(--font-mono)", fontSize: 11 }}>
              <span style={{ color: "var(--sx-muted)", letterSpacing: 0.5 }}>AI GROUNDING</span>
              {["search-grounded discovery", "cross-verified, 2nd pass", "links live-checked"].map((step, i, arr) => (
                <span key={step} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ background: "var(--sx-chip)", color: "var(--sx-forest)", padding: "4px 9px", borderRadius: 5 }}>{step}</span>
                  {i < arr.length - 1 && <span style={{ color: "var(--sx-muted-light)" }}>→</span>}
                </span>
              ))}
              <span style={{ color: "var(--sx-muted)", marginLeft: 4 }}>{formatDate(project.enrichment.checked_at.slice(0, 10))}</span>
            </div>
          )}
        </div>

        {project.gated && <GatedBanner />}

        <div style={{ display: "flex", flexWrap: "wrap", gap: 26, alignItems: "flex-start" }}>
          <main style={{ flex: "1 1 660px", minWidth: 0, display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Hero */}
            <section style={{ background: "#fff", border: "1px solid var(--sx-line)", borderRadius: 16, padding: "28px 30px 26px" }}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 20, alignItems: "flex-start", marginBottom: 22 }}>
                <div style={{ flex: "1 1 340px", minWidth: 0 }}>
                  <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, marginBottom: 12 }}>
                    <StatusPill status={project.status} />
                    <span style={{ fontSize: 13.5, color: "var(--sx-muted)" }}>{typeLabel(project.project_type)}</span>
                  </div>
                  <h1
                    style={{
                      fontFamily: "var(--font-display)",
                      fontSize: 35,
                      lineHeight: 1.09,
                      letterSpacing: -1.1,
                      fontWeight: 700,
                      margin: "0 0 10px",
                    }}
                  >
                    {toDisplayCase(project.name)}
                  </h1>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--sx-muted)", marginBottom: 7 }}>
                    {project.spx_id}
                    {project.first_seen_at && <span> · Source data pulled {formatDate(project.first_seen_at.slice(0, 10))}</span>}
                  </div>
                  {locationLine(project) && <div style={{ fontSize: 14.5 }}>{locationLine(project)}</div>}
                </div>

                <div style={{ flex: "0 0 auto", display: "flex", flexWrap: "wrap", gap: 10, alignItems: "flex-start" }}>
                  <ScoreCard score={project.score} />
                  {FIREBASE_AUTH_ENABLED && <PipelineBox projectId={project.id} />}
                </div>
              </div>

              {/* The read panel */}
              <div
                style={{
                  background: hasDocuments ? "var(--sx-forest)" : "var(--sx-page-bg)",
                  border: hasDocuments ? "none" : "1px solid var(--sx-line)",
                  borderRadius: 14,
                  padding: "22px 24px",
                }}
              >
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    letterSpacing: 2.2,
                    textTransform: "uppercase",
                    color: hasDocuments ? "var(--sx-muted-light)" : "var(--sx-green)",
                    marginBottom: 11,
                  }}
                >
                  The read
                </div>
                <p
                  style={{
                    fontFamily: "var(--font-display)",
                    fontSize: 21,
                    lineHeight: 1.36,
                    fontWeight: 600,
                    letterSpacing: -0.4,
                    color: hasDocuments ? "#fff" : "var(--sx-ink)",
                    margin: "0 0 15px",
                  }}
                >
                  {readHeadline}
                </p>
                <div style={{ display: readStatsAllZero ? "none" : "flex", flexWrap: "wrap", gap: 10 }}>
                  {readStats.map((s) => (
                    <div
                      key={s.text}
                      style={{
                        flex: "1 1 172px",
                        background: hasDocuments ? "rgba(255,255,255,0.09)" : "#fff",
                        borderRadius: 10,
                        padding: "14px 16px",
                      }}
                    >
                      <div
                        style={{
                          fontFamily: "var(--font-display)",
                          fontSize: 27,
                          fontWeight: 700,
                          letterSpacing: -1,
                          lineHeight: 1,
                          color: s.num === "0" ? (hasDocuments ? "var(--sx-muted-light)" : "var(--sx-faint)") : hasDocuments ? "#fff" : "var(--sx-forest)",
                        }}
                      >
                        {s.num}
                      </div>
                      <div style={{ fontSize: 12.5, lineHeight: 1.45, color: hasDocuments ? "var(--sx-on-forest)" : "var(--sx-muted)", marginTop: 5 }}>
                        {s.text}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Facts grid. Flex-wrap, not CSS grid: with a variable fact
                  count the last row is rarely full, and grid reserves that
                  row's remaining column tracks as real (if empty) space --
                  the row above's own bottom hairline plus the container's
                  right/bottom border then frame that empty space as a
                  hollow box. Flex items claim no space beyond their own
                  content, so an incomplete last row simply ends with
                  nothing to outline. Cells draw their own hairlines via
                  box-shadow. See Fact/AbsentFactCell. */}
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  background: "#fff",
                  border: "1px solid var(--sx-line)",
                  borderRadius: 12,
                  overflow: "hidden",
                  marginTop: 20,
                }}
              >
                {facts.map((f) => (
                  <Fact key={f.label} label={f.label} value={f.value} mono={f.mono} />
                ))}
                {project.square_footage ? (
                  <Fact label="Square footage" value={formatSf(project.square_footage)} />
                ) : (
                  <AbsentFactCell label="Square footage" reason="Not stated in the source record" />
                )}
                {project.owner ? (
                  <Fact label="Owner" value={toDisplayCase(project.owner)} />
                ) : (
                  <AbsentFactCell label="Owner" reason="Not disclosed in the source record" />
                )}
                {project.general_contractor || gcFact?.value ? (
                  <Fact label="General contractor" value={toDisplayCase(project.general_contractor || gcFact!.value)} />
                ) : (
                  <AbsentFactCell label="General contractor" reason="Unassigned, pre-award" />
                )}
                {project.architect || architectFact?.value ? (
                  <Fact label="Architect" value={toDisplayCase(project.architect || architectFact!.value)} />
                ) : (
                  <AbsentFactCell label="Architect" reason="Unlisted in the source record" />
                )}
              </div>
            </section>

            {/* Tabs */}
            <section style={{ background: "#fff", border: "1px solid var(--sx-line)", borderRadius: 16, overflow: "hidden" }}>
              <TabBar counts={tabCounts} />

              <div id="tab-panel-brief" style={{ padding: "24px 28px" }}>
                <h2 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 19, margin: "0 0 12px" }}>Executive brief</h2>
                <BriefTab project={project} />
              </div>

              <div id="tab-panel-scope" style={{ padding: "24px 28px", display: "none" }}>
                <ScopeTab csiScope={project.enrichment?.csi_scope} citations={citations} derivedScope={derivedScope} />
              </div>

              <div id="tab-panel-spec" style={{ padding: "24px 28px", display: "none" }}>
                <SpecificationTab
                  citations={citations}
                  governingRule={project.enrichment?.governing_rule}
                  documentCount={documentCount}
                  hasTeam={teamCount > 0}
                  hasScope={derivedScope.length > 0 || (project.enrichment?.csi_scope.length ?? 0) > 0}
                />
              </div>

              <div id="tab-panel-team" style={{ padding: "24px 28px", display: "none" }}>
                <TeamTab team={project.enrichment?.team} contacts={project.enrichment?.contact} />
              </div>

              <div id="tab-panel-documents" style={{ padding: "24px 28px", display: "none" }}>
                <DocumentsTab documents={project.documents} />
              </div>
            </section>
          </main>

          {/* Right rail */}
          <aside style={{ flex: "1 1 300px", position: "sticky", top: 86, display: "flex", flexDirection: "column", gap: 16 }}>
            {FIREBASE_AUTH_ENABLED && <ProjectAskPanel projectId={project.id} />}

            <ActivityFeed items={feedItems} />

            {project.enrichment?.contact.length ? (
              <div className="card p-5">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-gray-400)]">Contacts</h3>
                <dl className="mt-3 space-y-3">
                  {project.enrichment.contact.map((fact) => (
                    <div key={fact.field_key} className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <dt className="text-[10px] font-semibold uppercase tracking-wide text-[var(--color-gray-400)]">{fact.label}</dt>
                        <dd className="mt-0.5 text-xs break-words">{fact.value}</dd>
                      </div>
                    </div>
                  ))}
                </dl>
              </div>
            ) : null}

            <div style={{ background: "var(--sx-panel)", border: "1px solid var(--sx-line)", borderRadius: 12, padding: 16, fontSize: 12.5, color: "var(--sx-muted)", lineHeight: 1.5 }}>
              A finding cannot exist in SpecIndex without a source behind it.
            </div>
          </aside>
        </div>
      </div>
    </article>
  );
}
