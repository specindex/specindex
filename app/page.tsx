import type { Metadata } from "next";
import Link from "next/link";
import { HomePageGate } from "@/components/marketing/HomePageGate";
import { ProductMock } from "@/components/marketing/ProductMock";
import { StatsStrip } from "@/components/marketing/DemoSection";
import { RequestDemoButton } from "@/components/marketing/RequestDemoButton";
import { FAQ } from "@/components/marketing/FAQ";
import { getStats, getSampleProjects, getRecentCount, getDistinctCounties } from "@/lib/projects";
import { getVisibilitySnapshot } from "@/lib/stats";
import { getDivisionRollup, getMappedProjectCount } from "@/lib/divisions";

// Organization + SoftwareApplication JSON-LD -- a Gemini-reviewed finding
// in docs/architecture-2026/03-growth.md flagged this as the single
// highest-leverage SEO fix: zero marketing pages carry structured data
// today, so SpecIndex is invisible to rich-result surfaces (AI Overviews,
// sitelinks) a buyer's query increasingly resolves through. Kept outside
// HomePageGate so it describes the product/company regardless of
// signed-in state, not just the anonymous marketing view.
const homeJsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      name: "SpecIndex",
      url: "https://specindex.ai",
      logo: "https://specindex.ai/icon.svg",
      description: "Commercial construction project intelligence for building product manufacturers.",
    },
    {
      "@type": "SoftwareApplication",
      name: "SpecIndex",
      applicationCategory: "BusinessApplication",
      operatingSystem: "Web",
      description:
        "SpecIndex ranks open commercial construction projects by a transparent priority score, filtered by territory and product category.",
      offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
    },
  ],
};

const faqs = [
  {
    q: "Where does the project data come from?",
    a: "We maintain our own extensive, continuously updated database of commercial construction activity. We don't resell anyone's licensed plan room content.",
  },
  {
    q: "How current is the index?",
    a: "Projects go in as we find them. Every project page shows the date it was captured and links to the sources behind it, so you can check the original before you act on it.",
  },
  {
    q: "Can you tell me if my brand is in an actual specification?",
    a: "Not yet. Right now we report brand names found in project coverage. Reading full specification books is what we're building next.",
  },
  {
    q: "What do you need from us to start?",
    a: "Your brand names and the categories you sell. That's enough to run a check against the index.",
  },
  {
    q: "How is this different from a plan room?",
    a: "A plan room is set up for estimators who need to know what to price and when it's due. You need to know something else: whether the product decision has already been made, and whether your category is still open. That's what the index is organized around.",
  },
  {
    q: "How much of the country do you cover?",
    a: "Commercial projects in all 50 states, filterable by state and county. Depth varies by market.",
  },
];

const stages = [
  {
    stage: "Announced",
    window: "Window opening",
    body: "Owner, site, and scale are announced. Nothing is drawn yet.",
    detail: "Too early for product detail, but early enough to get known by the design team.",
  },
  {
    stage: "Design and permitting",
    window: "Window open",
    body: "Drawings and specifications take shape. A basis of design gets named.",
    detail: "This is the stage that decides whether your product is even eligible.",
  },
  {
    stage: "Bidding",
    window: "Window closing",
    body: "Documents are issued. Substitution requests carry deadlines.",
    detail: "You can still get added here, but it takes an approval rather than a conversation.",
  },
  {
    stage: "Under construction",
    window: "Mostly closed",
    body: "Structure and envelope are committed. Long lead equipment is bought.",
    detail: "Interiors, finishes, and FF&E packages are still in play on plenty of jobs.",
  },
];

export const metadata: Metadata = {
  title: "SpecIndex — Commercial construction projects, ranked for manufacturers",
  description:
    "SpecIndex ranks open commercial construction projects by a transparent priority score, filtered to your territory and product category — top-of-funnel leads for building product manufacturers.",
  alternates: { canonical: "/" },
};

export default async function HomePage() {
  // getProjects()+getCorpus() used to fetch the ENTIRE corpus (~175K+ rows,
  // headed to 6.5M+) just to derive a handful of numbers -- timed out the
  // build the same way /projects/[id] did (see docs/ROADMAP.md item 44's
  // follow-up). total/states/recent/county-count now come from cheap SQL
  // aggregates that don't scale with corpus size; only the brand/division/
  // map rollups -- which need to inspect actual project fields, not just
  // count rows -- fall back to a bounded representative sample.
  // Sequential, not Promise.all -- confirmed live 2026-07-29 that the exact
  // same 4 calls resolve in ~14s standalone in plain Node, but this page
  // hung for the full 300s timeout on every attempt when they ran
  // concurrently inside this Server Component during static export.
  // Whatever the interaction is (React/Next's request-scoped fetch cache
  // and Promise.all don't seem to be a good mix during prerendering),
  // sequential awaits sidestep it entirely and cost a few extra seconds,
  // not 300 of them.
  const stats = await getStats();
  const recent = await getRecentCount(90);
  const counties = await getDistinctCounties();
  const sample = await getSampleProjects(2000);
  const count = stats.total;
  const stateCount = stats.states;
  const countyCount = counties.length;
  const brandScan = getVisibilitySnapshot(sample, "Acuity Brands", "lighting");
  const divisions = getDivisionRollup(sample);
  const mappedCount = getMappedProjectCount(sample);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(homeJsonLd) }}
      />
    <HomePageGate>
      {/* Hero */}
      <section className="bg-[var(--color-bg)]">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 py-16 md:grid-cols-2 md:px-8 md:py-24">
          <div>
            <p className="text-eyebrow">
              Top of funnel leads for building product manufacturers
            </p>
            <h1 className="mt-4 text-hero">
              The commercial projects your sales team should chase this week, ranked.
            </h1>
            <p className="mt-5 max-w-lg text-base leading-relaxed text-[var(--color-gray-600)]">
              SpecIndex ranks open commercial projects by a transparent priority
              score, filtered to your territory and product category — not a
              database dump of every permit in the state.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <RequestDemoButton className="btn btn-demo" />
              <Link href="/projects/" className="btn btn-outline">
                Search the index
              </Link>
              <Link href="/visibility/" className="btn btn-outline">
                Run a brand check
              </Link>
            </div>
            <p className="mt-6 text-sm text-[var(--color-gray-400)]">
              Currently tracking commercial work in{" "}
              {stateCount === 1 ? "1 state" : `${stateCount} states`}.
            </p>
          </div>
          <ProductMock />
        </div>
      </section>

      <StatsStrip
        stats={[
          { value: `${count}+`, label: "Open commercial projects indexed nationwide" },
          { value: `${recent}+`, label: "Projects with activity in the last 90 days" },
          {
            value: `${stateCount}`,
            label: stateCount === 1 ? "State with active commercial work" : "States with active commercial work",
          },
          { value: `${countyCount}`, label: "Counties with indexed projects" },
        ]}
      />

      {/* Problem */}
      <section className="bg-white">
        <div className="mx-auto max-w-3xl px-5 py-20 text-center md:px-8">
          <h2 className="text-section">
            Specs get written in rooms you&apos;re not in.
          </h2>
          <p className="mt-5 text-base leading-relaxed text-[var(--color-gray-600)]">
            An architect names a basis of design. An engineer publishes an approved
            manufacturers list. A substitution deadline comes and goes. Every one of
            those moments affects whether your product is eligible, and all of them
            happen before a purchase order exists.
          </p>
          <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
            Most of that information exists somewhere. The trouble is that it&apos;s
            scattered across thousands of markets, and every one of them presents it
            differently.
          </p>
        </div>
      </section>

      {/* Spec window timeline */}
      <section className="border-t border-[var(--color-border)] bg-[var(--color-gray-100)]">
        <div className="mx-auto max-w-6xl px-5 py-20 md:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-section">Every project has a window. Then it closes.</h2>
            <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
              The same job is worth a very different call depending on how far along
              it is. We record the stage so you can sort that out before you pick up
              the phone.
            </p>
          </div>
          <ol className="mt-14 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {stages.map((s, i) => (
              <li
                key={s.stage}
                className="card flex flex-col p-5"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-mono text-xs font-semibold text-[var(--color-gray-400)]">
                    0{i + 1}
                  </span>
                  <span className="pill">{s.window}</span>
                </div>
                <h3 className="mt-3 text-base font-semibold">{s.stage}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--color-gray-600)]">
                  {s.body}
                </p>
                <p className="mt-3 text-xs leading-relaxed text-[var(--color-gray-400)]">
                  {s.detail}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Feature 1 */}
      <section className="border-t border-[var(--color-border)] bg-[var(--color-bg)]">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 py-20 md:grid-cols-2 md:px-8">
          <div>
            <p className="section-label">The index</p>
            <h2 className="text-section">See the projects your pipeline hasn&apos;t heard about yet.</h2>
            <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
              Commercial work in every state, from mixed use and healthcare to
              industrial, hospitality, and data centers. Each record carries the
              stage, value, project team, and what the job will need.
            </p>
            <Link href="/projects/" className="mt-6 inline-block text-sm font-semibold text-[var(--color-green)] hover:underline">
              Search the index →
            </Link>
          </div>
          <div className="card p-5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
              Sample project record
            </p>
            <h4 className="mt-2 text-lg font-semibold">Horizon 16 Industrial Park Phase II</h4>
            <p className="text-sm text-[var(--color-gray-600)]">Savannah, Chatham County</p>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-[var(--color-gray-400)]">Status</dt>
                <dd className="font-medium">Under construction</dd>
              </div>
              <div>
                <dt className="text-[var(--color-gray-400)]">Square footage</dt>
                <dd className="font-medium">1.5M SF</dd>
              </div>
              <div>
                <dt className="text-[var(--color-gray-400)]">General contractor</dt>
                <dd className="font-medium">Evans</dd>
              </div>
              <div>
                <dt className="text-[var(--color-gray-400)]">Watch</dt>
                <dd className="font-medium">High-bay lighting, dock doors</dd>
              </div>
            </dl>
          </div>
        </div>
      </section>

      {/* Feature 2 */}
      <section className="border-t border-[var(--color-border)] bg-white">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 py-20 md:grid-cols-2 md:px-8">
          <div className="order-2 md:order-1">
            <div className="card max-w-sm p-4 font-mono text-xs">
              <p className="text-[var(--color-gray-400)]">9:41</p>
              <div className="mt-3 flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded bg-[var(--color-green)] text-[8px] font-bold text-white">
                  S
                </span>
                <span className="font-semibold">SpecIndex</span>
              </div>
              <p className="mt-3 leading-relaxed text-[var(--color-gray-700)]">
                {brandScan.categoryHits.length} of our {sample.length} highest-priority
                scored projects will need lighting. {brandScan.stillOpen.length} are
                still in planning or permitting with no manufacturer named, so those
                are the ones worth a call this week.
              </p>
              <p className="mt-2 text-[var(--color-gray-400)]">9:42 AM</p>
            </div>
          </div>
          <div className="order-1 md:order-2">
            <p className="section-label">Brand visibility</p>
            <h2 className="text-section">Check where your name already shows up.</h2>
            <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
              Run your brand against the index and you&apos;ll see how many projects
              need your category, how many are still early, and how many name a
              manufacturer at all.
            </p>
            <Link href="/visibility/" className="mt-6 inline-block text-sm font-semibold text-[var(--color-green)] hover:underline">
              Run a brand check →
            </Link>
          </div>
        </div>
      </section>

      {/* Division segmentation */}
      <section className="border-t border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl px-5 py-20 md:px-8">
          <div className="max-w-3xl">
            <p className="section-label">Find your division</p>
            <h2 className="text-section">
              Sorted the way specs are written, not the way crews are hired.
            </h2>
            <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
              A spec book is organized by CSI MasterFormat division, so that&apos;s how
              we organize the index. It matters because trade labels overlap: lighting
              and switchgear are both Division 26 and both land on the electrical
              engineer&apos;s desk, so treating them as separate markets counts the same
              buyer twice.
            </p>
            <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
              Each division below shows how many indexed projects will need it, how
              many are still early enough to influence, and who normally writes it
              into the spec. That last column is the one your reps care about, because
              it tells them whose desk to get to.
            </p>
          </div>

          <div className="mt-10 overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="px-3 py-3 text-left font-semibold">Division</th>
                  <th className="px-3 py-3 text-left font-semibold">What you sell</th>
                  <th className="px-3 py-3 text-right font-semibold">Projects</th>
                  <th className="px-3 py-3 text-right font-semibold">Still early</th>
                  <th className="px-3 py-3 text-left font-semibold">Usually specified by</th>
                </tr>
              </thead>
              <tbody>
                {divisions.map((d) => (
                  <tr
                    key={d.code}
                    className="border-b border-[var(--color-border)] last:border-0"
                  >
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      <span className="font-mono text-xs font-semibold text-[var(--color-green)]">
                        {d.code}
                      </span>{" "}
                      <span className="font-medium">{d.name}</span>
                    </td>
                    <td className="px-3 py-2.5 text-[var(--color-gray-600)]">{d.plain}</td>
                    <td className="px-3 py-2.5 text-right font-mono">{d.projects}</td>
                    <td className="px-3 py-2.5 text-right font-mono font-semibold text-[var(--color-green)]">
                      {d.stillOpen}
                    </td>
                    <td className="px-3 py-2.5 text-[var(--color-gray-600)]">
                      {d.specifiedBy}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-sm text-[var(--color-gray-400)]">
            Counted across our {sample.length} highest-priority scored projects (of{" "}
            {count} indexed nationwide), {mappedCount} of which need at least one of
            these divisions. A project appears in every division it needs, so the
            column adds up to more than {sample.length}.
          </p>
        </div>
      </section>

      {/* Funnel position */}
      <section className="border-t border-[var(--color-border)] bg-[var(--color-gray-100)]">
        <div className="mx-auto max-w-3xl px-5 py-20 md:px-8">
          <h2 className="text-section">This is the top of your funnel.</h2>
          <p className="mt-5 text-base leading-relaxed text-[var(--color-gray-600)]">
            By the time a job reaches your quote log, the interesting decisions have
            been made. SpecIndex sits earlier than that. It answers the question a rep
            has on Monday morning: which projects in my territory exist, which ones
            need what I sell, and which are early enough that a conversation still
            changes the outcome.
          </p>
          <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
            Everything downstream stays where it is. Your CRM still holds the
            relationship, your quoting stays in your system, your distributors keep
            their role. What you get here is the list that feeds all of it, with a
            source link on every project so a rep can verify it before making the
            call.
          </p>
        </div>
      </section>

      {/* Positioning */}
      <section className="border-t border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-3xl px-5 py-20 md:px-8">
          <h2 className="text-section">Bid boards were built for the people doing the buying.</h2>
          <p className="mt-5 text-base leading-relaxed text-[var(--color-gray-600)]">
            Plan rooms and project databases are organized around what an estimator
            needs: what do I price, and when is it due. That&apos;s a perfectly good
            question, but it isn&apos;t yours.
          </p>
          <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
            What you need to know is whether the product decision has been made yet,
            who&apos;s making it, and whether your category is still open. So we
            organized the index around stage, product category, and whether anyone
            has been named.
          </p>
        </div>
      </section>

      <FAQ items={faqs} />
    </HomePageGate>
    </>
  );
}
