import type { Metadata } from "next";
import Link from "next/link";
import { RequestDemoButton } from "@/components/marketing/RequestDemoButton";
import { getSampleProjects } from "@/lib/projects";
import {
  CRH_CATEGORY_KEYWORDS,
  countProjectsNamingAny,
  getCapturedCoverage,
  getCategoryBucket,
  getGcLeaderboard,
  getReportingGaps,
  type Coverage,
} from "@/lib/reporting";
import { isStillOpen } from "@/lib/stats";

export const metadata: Metadata = {
  title: "Reporting",
  description:
    "The project lifecycle record: who bid, who won, and which products were installed. Every figure on this page is computed from the live index.",
};

const CRH_BRANDS = [
  "Belgard",
  "Echelon Masonry",
  "Sakrete",
  "Amerimix",
  "MoistureShield",
  "RDI",
  "Catalyst",
  "Techniseal",
];

export default async function ReportingPage() {
  // Was getProjects() (the entire ~175K+-row corpus, ~1,750 sequential API
  // calls). That's what this page's own copy used to promise ("None of it
  // is a sample or a projection") -- true until 2026-07-29, when it became
  // the reason /reporting's build kept failing: that many requests, even
  // paced, exhausts the API's small connection pool badly enough to starve
  // *other* pages building in parallel, not just this one (confirmed live:
  // homepage timed out too, despite needing none of this itself). Bounded
  // to the same representative sample every other stats page now uses.
  // Real fix is dedicated SQL aggregate endpoints so this can be both fast
  // and exact again; until then the copy below says "sample," honestly,
  // instead of silently breaking its own claim.
  const projects = await getSampleProjects(2000);
  const total = projects.length;

  const captured = getCapturedCoverage(projects);
  const gaps = getReportingGaps(projects);
  const gc = getGcLeaderboard(projects);

  const crh = getCategoryBucket(projects, CRH_CATEGORY_KEYWORDS);
  const crhOpen = crh.projects.filter(isStillOpen);
  const crhNamed = countProjectsNamingAny(projects, ["CRH", "Oldcastle", ...CRH_BRANDS]);

  return (
    <div className="bg-[var(--color-bg)]">
      {/* Hero */}
      <section className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-4xl px-5 py-16 md:px-8 md:py-20">
          <p className="text-eyebrow">Reporting</p>
          <h1 className="mt-3 text-hero">
            One project ID, and everything that happened to it.
          </h1>
          <p className="mt-5 text-base leading-relaxed text-[var(--color-gray-600)]">
            The index tells you a project exists and what it will need. Reporting is
            the other half: who bid, who won, which subcontractor took each division,
            and what actually got installed, all hanging off one project ID that stays
            the same from announcement through completion.
          </p>
          <p className="mt-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-gray-100)] p-4 text-sm leading-relaxed text-[var(--color-gray-600)]">
            <strong className="text-[var(--color-ink)]">
              Every number below is a real, live query result — computed from our
              {" "}{total} highest-priority scored projects, not the full index.
            </strong>{" "}
            None of it is fabricated or projected forward from a formula; it&apos;s
            counted directly. It&apos;s currently a large representative sample rather
            than every project in the index, a deliberate tradeoff to keep this page
            fast while we build dedicated full-index aggregate queries. Several
            figures below are zero, which means we haven&apos;t captured that data yet.
          </p>
        </div>
      </section>

      {/* What is captured today */}
      <section className="border-b border-[var(--color-border)]">
        <div className="mx-auto max-w-4xl px-5 py-16 md:px-8">
          <h2 className="text-section">What the index captures today</h2>
          <p className="mt-3 text-base leading-relaxed text-[var(--color-gray-600)]">
            Counted across our {total} highest-priority scored projects. Coverage is lumpy because
            permit records name an owner far more reliably than they name an architect
            or a contractor.
          </p>
          <div className="mt-8 space-y-2.5">
            {captured.map((c) => (
              <CoverageRow key={c.field} c={c} tone="captured" />
            ))}
          </div>
        </div>
      </section>

      {/* The reporting gap */}
      <section className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-4xl px-5 py-16 md:px-8">
          <h2 className="text-section">What reporting has to add</h2>
          <p className="mt-3 text-base leading-relaxed text-[var(--color-gray-600)]">
            These are the fields that turn a project from a snapshot into a full
            lifecycle record, and every one of them currently reads zero. Bid tabs,
            award notices, and closeout documents exist in plenty of jurisdictions.
            Tying them back to the right project is most of the work.
          </p>
          <div className="mt-8 space-y-2.5">
            {gaps.map((c) => (
              <CoverageRow key={c.field} c={c} tone="gap" />
            ))}
          </div>
          <p className="mt-6 text-sm leading-relaxed text-[var(--color-gray-400)]">
            Bid tabs, award notices, and closeout documents are public in plenty of
            jurisdictions. The catch is that they get published separately from the
            original permit and rarely reference it, so tying them back to the right
            project is most of the effort.
          </p>
        </div>
      </section>

      {/* GC leaderboard - real but small sample */}
      <section className="border-b border-[var(--color-border)]">
        <div className="mx-auto max-w-4xl px-5 py-16 md:px-8">
          <h2 className="text-section">What a lifecycle query looks like now</h2>
          <p className="mt-3 text-base leading-relaxed text-[var(--color-gray-600)]">
            General contractors ranked by how many indexed projects name them. This is
            a real query against real data, and it also shows the problem: it can only
            see{" "}
            <strong className="text-[var(--color-ink)]">
              {gc.sampleSize} of {total} sampled projects
            </strong>{" "}
            ({Math.round((gc.sampleSize / total) * 100)}%), because the rest do not
            name a contractor in any public source we have read.
          </p>
          <div className="mt-8 overflow-hidden rounded-lg border border-[var(--color-border)] bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] bg-[var(--color-gray-100)]">
                  <th className="px-4 py-3 text-left font-semibold">General contractor</th>
                  <th className="px-4 py-3 text-right font-semibold">Projects</th>
                </tr>
              </thead>
              <tbody>
                {gc.rows.map((r) => (
                  <tr key={r.name} className="border-b border-[var(--color-border)] last:border-0">
                    <td className="px-4 py-2.5">{r.name}</td>
                    <td className="px-4 py-2.5 text-right font-mono">{r.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-sm text-[var(--color-gray-400)]">
            {gc.distinct} different contractor names across {gc.sampleSize} projects,
            which is why the counts are so small. Add award notices to this and the
            same query starts to look like a market share report.
          </p>
        </div>
      </section>

      {/* CRH reference account */}
      <section className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-4xl px-5 py-16 md:px-8">
          <p className="section-label">Reference account</p>
          <h2 className="text-section">CRH / Oldcastle</h2>
          <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
            CRH is NYSE-listed and a member of the S&amp;P 500. Its Americas Materials
            Solutions business is headquartered in Dunwoody, Georgia, and Oldcastle APG
            has offices at 400 Perimeter Center Terrace in Atlanta. Oldcastle
            Infrastructure operates at least four facilities in Georgia and lists more
            than 16,000 pipe, precast, stormwater and enclosure products. In 2026 CRH
            announced a $1.7M shared services center in Roswell that will bring its
            Georgia headcount to roughly 1,400 by 2029.
          </p>
          <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
            That makes CRH a natural reference account for an index started in Georgia.
            Their product lines run through concrete, paving, precast, masonry and
            hardscape, which get specified early and then installed by subcontractors
            whose names rarely make it back to the manufacturer.
          </p>

          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            <Metric
              value={String(crh.projects.length)}
              label={`of our ${total} sampled projects need a CRH product category`}
            />
            <Metric
              value={String(crhOpen.length)}
              label="of those are still in planning or permitting"
            />
            <Metric
              value={String(crhNamed)}
              label="name CRH, Oldcastle, or any Oldcastle brand"
              muted={crhNamed === 0}
            />
          </div>

          <div className="mt-6 rounded-lg border border-[var(--color-amber)] bg-[#fffbeb] p-4">
            <p className="text-sm font-semibold text-[var(--color-ink)]">
              Read that third number carefully
            </p>
            <p className="mt-1.5 text-sm leading-relaxed text-[var(--color-gray-600)]">
              {crhNamed === 0
                ? `Across our ${total} sampled projects, not one public source we have read names CRH, Oldcastle, or any of their brands: `
                : `Across our ${total} sampled projects, only ${crhNamed} name CRH, Oldcastle, or any of their brands: `}
              Belgard, Echelon Masonry, Sakrete, Amerimix, MoistureShield, RDI,
              Catalyst, or Techniseal. That says nothing about how much of this market
              CRH holds, which is a great deal of it. It says what permits and press
              releases contain, and they almost never contain manufacturer names. We
              could only show a share of spec figure here by making one up.
            </p>
          </div>

          <h3 className="mt-10 text-lg font-semibold">
            The categories driving those {crh.projects.length} projects
          </h3>
          <div className="mt-4 flex flex-wrap gap-2">
            {crh.byCategory.map((c) => (
              <span
                key={c.name}
                className="rounded-full border border-[var(--color-border)] bg-[var(--color-gray-100)] px-3 py-1 text-xs"
              >
                {c.name}{" "}
                <span className="font-mono font-semibold text-[var(--color-green)]">
                  {c.count}
                </span>
              </span>
            ))}
          </div>
          <p className="mt-4 text-sm text-[var(--color-gray-400)]">
            These add up to more than {crh.projects.length} because a single project
            often needs several of them.
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-[var(--color-gray-100)]">
        <div className="mx-auto max-w-3xl px-5 py-16 text-center md:px-8">
          <h2 className="text-section">Want lifecycle reporting for your categories?</h2>
          <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
            Tell us the divisions you sell and the states you care about. We will show
            you exactly what the index holds on them today, including the gaps.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <RequestDemoButton className="btn btn-primary" />
            <Link href="/projects/" className="btn btn-outline">
              Search the index
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function CoverageRow({ c, tone }: { c: Coverage; tone: "captured" | "gap" }) {
  const empty = c.present === 0;
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-white p-3.5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-sm font-semibold text-[var(--color-ink)]">{c.label}</span>
        <span
          className={`font-mono text-xs font-semibold ${
            empty ? "text-[var(--color-gray-400)]" : "text-[var(--color-green)]"
          }`}
        >
          {empty ? "not captured yet" : `${c.present} / ${c.total} · ${c.pct}%`}
        </span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-gray-200)]">
        <div
          className={`h-full rounded-full ${
            tone === "gap" ? "bg-[var(--color-amber)]" : "bg-[var(--color-green)]"
          }`}
          style={{ width: `${c.pct}%` }}
        />
      </div>
      <p className="mt-2 text-xs text-[var(--color-gray-400)]">{c.note}</p>
    </div>
  );
}

function Metric({
  value,
  label,
  muted,
}: {
  value: string;
  label: string;
  muted?: boolean;
}) {
  return (
    <div className="card p-5">
      <p
        className={`font-mono text-3xl font-bold ${
          muted ? "text-[var(--color-gray-400)]" : "text-[var(--color-green)]"
        }`}
      >
        {value}
      </p>
      <p className="mt-2 text-sm leading-snug text-[var(--color-gray-600)]">{label}</p>
    </div>
  );
}
