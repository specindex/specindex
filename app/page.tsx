import type { Metadata } from "next";
import Link from "next/link";
import { HomePageGate } from "@/components/marketing/HomePageGate";
import { ProductMock } from "@/components/marketing/ProductMock";
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
      description: "AI construction project intelligence for building product manufacturers.",
    },
    {
      "@type": "SoftwareApplication",
      name: "SpecIndex",
      applicationCategory: "BusinessApplication",
      operatingSystem: "Web",
      description:
        "SpecIndex tracks permits, bids, and awards across all 50 states, then uses AI to score every project for a manufacturer's product category and territory.",
      offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
    },
  ],
};

// Rebuilt 2026-07-31 from a Claude-Projects mockup + build brief (see
// docs/ROADMAP.md item 92). Trust model at this stage, per the brief: no
// customers yet, so credibility comes only from the real live product and
// real data -- no fake logos, testimonials, or compliance badges, and no
// founder name/photo (company is in stealth). Copy rule: no em-dashes
// anywhere in visible text.
const faqs = [
  {
    q: "How early is this, really?",
    a: "Early, and we are not hiding it. The data pipeline is live and already tracking real projects across all 50 states, but we are building the product around a small group of early access partners. If you want influence over a tool before it is set in stone, this is the moment.",
  },
  {
    q: "What's expected of an early access partner?",
    a: "Roughly a 30 minute onboarding and a short working session every week or two. You tell us what is useful, what is noise, and what would make you actually change how you chase specs. In return you help set the roadmap.",
  },
  {
    q: "Do I have to pay?",
    a: "No. Early access partners use SpecIndex free through the beta, and lock in founding pricing for life when we launch.",
  },
  {
    q: "Where does the data come from?",
    a: "Directly from county, municipal, and state permit systems, public bid boards, and award notices. Every record links back to its original public source. We do not resell third-party plan room feeds.",
  },
  {
    q: "Who is it a fit for?",
    a: "Building product manufacturers with a field sales or specification team who want to influence projects at design and permitting, before the spec is written.",
  },
];

const pipeline = [
  {
    n: "01",
    title: "Discover",
    body: "AI continuously scans permit, bid, and award sources across every state, county, and municipality, the moment records are filed.",
  },
  {
    n: "02",
    title: "Enrich & score",
    body: "Each project is ranked by stage, value, and fit to your product category, then enriched with the decision makers who write the spec.",
  },
  {
    n: "03",
    title: "Deliver",
    body: "Filtered results with source links for verification, pushed to your feed or pulled by your own agents. No plan room resale, ever.",
  },
];

// Only REST API is real today (see docs/ROADMAP.md item 92) -- MCP server,
// Snowflake, and Databricks are logged as roadmap items, not shipped, so
// they're marked "coming" rather than presented as live integrations.
const integrations = [
  { name: "REST API", live: true },
  { name: "CSV / Excel export", live: false },
  { name: "MCP server", live: false },
  { name: "Snowflake", live: false },
  { name: "Databricks", live: false },
];

export const metadata: Metadata = {
  title: "SpecIndex | AI construction project intelligence for building product manufacturers",
  description:
    "SpecIndex tracks permits, bids, and awards across all 50 states, then uses AI to score every project for your product category and surface it months before it reaches the trade press.",
  alternates: { canonical: "/" },
};

export default async function HomePage() {
  const stats = await getStats();
  const recent = await getRecentCount(30);
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
              <div className="flex flex-wrap items-center gap-2.5">
                <span className="inline-flex items-center gap-2 rounded-full border border-[#bfe6cf] bg-[#e8f6ee] px-3 py-1.5 text-xs font-semibold text-[#166534]">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-green)]" />
                  Early access now open
                </span>
                <span className="inline-flex items-center rounded-full border border-[var(--color-border)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--color-gray-600)]">
                  AI-native &middot; MCP-ready
                </span>
              </div>
              <h1 className="mt-5 text-hero">
                Win the spec <span className="text-[var(--color-green)]">before your competitors know the project exists.</span>
              </h1>
              <p className="mt-5 max-w-lg text-base leading-relaxed text-[var(--color-gray-600)]">
                SpecIndex is AI construction project intelligence for building product
                manufacturers. We track permits, bids, and awards across all{" "}
                {stateCount} states, then use AI to score every project for your
                product category and surface it months before it reaches the trade
                press.
              </p>
              <ul className="mt-5 grid gap-2.5">
                <li className="flex items-start gap-2.5 text-[15px] text-[var(--color-ink)]">
                  <span className="mt-0.5 font-bold text-[var(--color-green)]">&#10003;</span>
                  <span>Every project ranked by an AI priority score for your category and territory</span>
                </li>
                <li className="flex items-start gap-2.5 text-[15px] text-[var(--color-ink)]">
                  <span className="mt-0.5 font-bold text-[var(--color-green)]">&#10003;</span>
                  <span>Spec opportunities surfaced at design and permitting, not at bid when it is already too late</span>
                </li>
                <li className="flex items-start gap-2.5 text-[15px] text-[var(--color-ink)]">
                  <span className="mt-0.5 font-bold text-[var(--color-green)]">&#10003;</span>
                  <span>Straight from public source records. No plan room resale.</span>
                </li>
              </ul>
              <div className="mt-8 flex flex-wrap gap-3">
                <RequestDemoButton className="btn btn-demo">Get early access &rarr;</RequestDemoButton>
                <Link href="/projects/" className="btn btn-outline">
                  See live coverage
                </Link>
              </div>
              <p className="mt-4 flex items-center gap-2 text-[13px] text-[var(--color-gray-400)]">
                <span className="text-[var(--color-green)]">&#9679;</span>
                Founder-led &middot; Free during the beta &middot; You help shape the product
              </p>
            </div>
            <ProductMock />
          </div>
        </section>

        {/* Proof strip -- honest: the product is real, not a mockup */}
        <section className="border-y border-[var(--color-border)] bg-[var(--color-gray-100)] py-6">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-3 px-5 text-center md:px-8">
            <span className="inline-flex items-center gap-2 rounded-full border border-[#bfe6cf] bg-[#e8f6ee] px-3 py-1.5 text-xs font-semibold text-[#166534]">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-green)]" />
              Pipeline live
            </span>
            <span className="text-sm font-semibold text-[var(--color-ink)]">
              This is not a mockup. The index is already running.
            </span>
            <span className="text-sm text-[var(--color-gray-600)]">
              Real projects, real permit data, updated continuously across all 50 states.
            </span>
          </div>
        </section>

        {/* Live stats -- pulled from the index on every render, not a screenshot */}
        <section className="bg-white">
          <div className="mx-auto max-w-6xl px-5 py-16 md:px-8">
            <p className="section-label text-center">Live today</p>
            <h2 className="text-section mt-2 text-center">What&apos;s in the index right now</h2>
            <div className="mt-10 grid grid-cols-2 gap-4 md:grid-cols-4">
              <div className="card p-6 text-center">
                <div className="font-mono text-3xl font-bold tabular-nums text-[var(--color-ink)]">
                  {count.toLocaleString()}
                  <span className="text-[var(--color-green)]">+</span>
                </div>
                <div className="mt-1.5 text-[13px] text-[var(--color-gray-600)]">Projects tracked</div>
              </div>
              <div className="card p-6 text-center">
                <div className="font-mono text-3xl font-bold tabular-nums text-[var(--color-ink)]">
                  {recent.toLocaleString()}
                  <span className="text-[var(--color-green)]">+</span>
                </div>
                <div className="mt-1.5 text-[13px] text-[var(--color-gray-600)]">Active in last 30 days</div>
              </div>
              <div className="card p-6 text-center">
                <div className="font-mono text-3xl font-bold tabular-nums text-[var(--color-ink)]">{stateCount}</div>
                <div className="mt-1.5 text-[13px] text-[var(--color-gray-600)]">States covered</div>
              </div>
              <div className="card p-6 text-center">
                <div className="font-mono text-3xl font-bold tabular-nums text-[var(--color-ink)]">{countyCount}</div>
                <div className="mt-1.5 text-[13px] text-[var(--color-gray-600)]">Counties indexed</div>
              </div>
            </div>
          </div>
        </section>

        {/* How it works */}
        <section className="border-t border-[var(--color-border)] bg-[var(--color-gray-100)]">
          <div className="mx-auto max-w-6xl px-5 py-20 md:px-8">
            <div className="mx-auto max-w-2xl text-center">
              <p className="section-label">The pipeline</p>
              <h2 className="text-section mt-2">From public record to prioritized opportunity</h2>
              <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
                Anyone can aggregate permits. SpecIndex scores, enriches, and verifies
                them so you work the right projects first.
              </p>
            </div>
            <div className="mt-12 grid gap-5 md:grid-cols-3">
              {pipeline.map((step) => (
                <div key={step.n} className="card p-6">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#bfe6cf] bg-[#e8f6ee] font-mono text-sm font-bold text-[var(--color-green)]">
                    {step.n}
                  </div>
                  <h3 className="mt-4 text-lg font-semibold">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-[var(--color-gray-600)]">{step.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Win the spec */}
        <section className="border-t border-[var(--color-border)] bg-white">
          <div className="mx-auto max-w-6xl px-5 py-20 md:px-8">
            <div className="mx-auto max-w-2xl text-center">
              <p className="section-label">Win the spec</p>
              <h2 className="text-section mt-2">Track your specification share, and your competitors&apos;.</h2>
              <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
                SpecIndex doesn&apos;t just find projects. It shows you where your name
                already appears, where a competitor is winning the spec, and which
                decision maker to reach before the window closes.
              </p>
            </div>

            <div className="mt-14 grid items-start gap-12 md:grid-cols-2">
              <div>
                <h3 className="text-lg font-semibold">Check where your name already shows up</h3>
                <p className="mt-3 text-sm leading-relaxed text-[var(--color-gray-600)]">
                  Run your brand against the index and you&apos;ll see how many projects
                  need your category, how many are still early, and how many name a
                  manufacturer at all.
                </p>
                <div className="card mt-5 p-4 font-mono text-xs">
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
                </div>
                <Link href="/visibility/" className="mt-5 inline-block text-sm font-semibold text-[var(--color-green)] hover:underline">
                  Run a brand check &rarr;
                </Link>
              </div>

              <div>
                <h3 className="text-lg font-semibold">Spec share by MasterFormat division</h3>
                <p className="mt-3 text-sm leading-relaxed text-[var(--color-gray-600)]">
                  A spec book is organized by CSI MasterFormat division, so that&apos;s how
                  we organize the index. Each row shows how many indexed projects need
                  it, how many are still early enough to influence, and who normally
                  writes it into the spec.
                </p>
                <div className="card mt-5 overflow-hidden">
                  <div className="flex items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-gray-100)] px-4 py-3 text-xs text-[var(--color-gray-600)]">
                    <span>Product category coverage</span>
                    <span className="flex items-center gap-1.5">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-green)]" />
                      Early stage
                    </span>
                  </div>
                  <div className="max-h-[280px] overflow-y-auto">
                    {divisions.slice(0, 8).map((d) => (
                      <div
                        key={d.code}
                        className="flex items-center gap-3 border-b border-[var(--color-border)] px-4 py-3 text-sm last:border-0"
                      >
                        <span className="inline-block h-1.5 w-1.5 flex-none rounded-full bg-[var(--color-green)]" />
                        <span className="flex-1 font-medium">{d.name}</span>
                        <span className="font-mono font-semibold">{d.projects.toLocaleString()}</span>
                        <span className="hidden w-32 text-right text-xs text-[var(--color-gray-400)] sm:inline">
                          {d.specifiedBy}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
                <p className="mt-3 text-xs text-[var(--color-gray-400)]">
                  Counted across our {sample.length} highest-priority scored projects
                  (of {count.toLocaleString()} indexed nationwide), {mappedCount} of
                  which need at least one of these divisions.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Why we're building it -- stealth, no founder identity */}
        <section className="border-t border-[var(--color-border)] bg-[var(--color-gray-100)]">
          <div className="mx-auto max-w-2xl px-5 py-20 text-center md:px-8">
            <p className="section-label">Why we&apos;re building SpecIndex</p>
            <h2 className="text-section mt-3">
              Manufacturers find out about the right projects too late, usually at bid,
              once the spec is already written.
            </h2>
            <p className="mt-5 text-base leading-relaxed text-[var(--color-gray-600)]">
              For years we watched building product teams lose specs they never knew
              were in play. By the time a project reached the trade press or a bid
              board, the engineer had already chosen, and it usually was not the
              company that found out last.
            </p>
            <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
              SpecIndex is the tool we wished those teams had. Every project in the
              country, scored by AI for your category, surfaced while the spec is
              still open. The index is live today. We are in stealth and building the
              rest alongside a small group of early access partners.
            </p>
            <p className="mt-6 text-sm font-semibold text-[var(--color-ink)]">
              The team behind SpecIndex
              <span className="mt-0.5 block text-xs font-normal text-[var(--color-gray-400)]">
                Operators with deep roots in the building products industry, currently in stealth
              </span>
            </p>
            <RequestDemoButton className="btn btn-demo mt-6">Get early access &rarr;</RequestDemoButton>
          </div>
        </section>

        {/* Early access program */}
        <section className="border-t border-[var(--color-border)] bg-white">
          <div className="mx-auto max-w-6xl px-5 py-20 md:px-8">
            <div className="mx-auto max-w-2xl text-center">
              <p className="section-label">Early access</p>
              <h2 className="text-section mt-2">Help shape it, and get an unfair advantage first.</h2>
              <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
                We&apos;re taking on a small group of building product manufacturers to
                build alongside. In exchange for your feedback, you get:
              </p>
            </div>
            <div className="mt-12 grid gap-5 md:grid-cols-3">
              <div className="card p-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#bfe6cf] bg-[#e8f6ee] text-lg text-[var(--color-green)]">&#9707;</div>
                <h4 className="mt-4 text-base font-semibold">Direct line to the team</h4>
                <p className="mt-1.5 text-sm text-[var(--color-gray-600)]">Weekly working sessions. Your workflows and product categories shape what we build next.</p>
              </div>
              <div className="card p-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#bfe6cf] bg-[#e8f6ee] text-lg text-[var(--color-green)]">&#10022;</div>
                <h4 className="mt-4 text-base font-semibold">Free during the beta</h4>
                <p className="mt-1.5 text-sm text-[var(--color-gray-600)]">No cost while we build together, plus founding partner pricing locked in for life when we launch.</p>
              </div>
              <div className="card p-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#bfe6cf] bg-[#e8f6ee] text-lg text-[var(--color-green)]">&#9678;</div>
                <h4 className="mt-4 text-base font-semibold">First-mover coverage</h4>
                <p className="mt-1.5 text-sm text-[var(--color-gray-600)]">Start seeing scored projects in your territory before anyone else in your category has access.</p>
              </div>
            </div>
            <div className="mt-10 flex flex-wrap justify-center gap-3">
              <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--color-ink)]">
                <span className="font-bold text-[var(--color-green)]">&#10003;</span> Limited to a handful of partners
              </span>
              <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--color-ink)]">
                <span className="font-bold text-[var(--color-green)]">&#10003;</span> Best fit: manufacturers with a field sales or spec team
              </span>
              <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-white px-4 py-2 text-[13px] font-medium text-[var(--color-ink)]">
                <span className="font-bold text-[var(--color-green)]">&#10003;</span> About 30 minutes to get started
              </span>
            </div>
            <div className="mt-8 flex justify-center">
              <RequestDemoButton className="btn btn-demo">Apply for early access &rarr;</RequestDemoButton>
            </div>
          </div>
        </section>

        {/* Delivered to your stack */}
        <section className="border-t border-[var(--color-border)] bg-[var(--color-gray-100)]">
          <div className="mx-auto max-w-6xl px-5 py-20 md:px-8">
            <div className="mx-auto max-w-2xl text-center">
              <p className="section-label">Delivered to your stack</p>
              <h2 className="text-section mt-2">Scored projects, straight into your workflow</h2>
              <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
                SpecIndex lands clean, source-linked project data wherever your team
                already works. Query it directly today; warehouse and CRM delivery are
                next on the roadmap.
              </p>
            </div>
            <div className="mt-10 flex flex-wrap justify-center gap-3">
              {integrations.map((i) => (
                <span
                  key={i.name}
                  className="inline-flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-white px-4 py-3 text-sm font-medium text-[var(--color-ink)] shadow-sm"
                >
                  {i.name}
                  {!i.live && <span className="font-normal text-[var(--color-gray-400)]">&middot; coming</span>}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* AI-native */}
        <section className="border-t border-[var(--color-border)] bg-white">
          <div className="mx-auto max-w-6xl px-5 py-20 md:px-8">
            <div className="mx-auto max-w-2xl text-center">
              <p className="section-label">AI-native</p>
              <h2 className="text-section mt-2">Built for how teams work now: AI, agents, and MCP</h2>
              <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
                SpecIndex is not a static database you log into. AI does the scoring,
                and we&apos;re building toward letting you ask it questions in plain
                language and connect your own agents directly.
              </p>
            </div>
            <div className="mt-12 grid gap-5 md:grid-cols-3">
              <div className="card p-6">
                <div className="text-lg text-[var(--color-green)]">&#9670;</div>
                <h3 className="mt-3 text-base font-semibold">AI scoring and enrichment</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--color-gray-600)]">Models rank every project by stage, value, and fit to your category, then surface the decision makers who write the spec. Signal, not noise.</p>
              </div>
              <div className="card p-6">
                <div className="text-lg text-[var(--color-green)]">&#10022;</div>
                <h3 className="mt-3 text-base font-semibold">Ask in plain language</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--color-gray-600)]">&quot;Show me hospital projects in Texas at permitting where a competitor is already specified.&quot; Query the whole index the way you would ask a colleague.<span className="ml-1.5 text-xs font-normal text-[var(--color-gray-400)]">(coming)</span></p>
              </div>
              <div className="card p-6">
                <div className="text-lg text-[var(--color-green)]">&#9889;</div>
                <h3 className="mt-3 text-base font-semibold">MCP server for your agents</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--color-gray-600)]">Connect SpecIndex over MCP so Claude and your internal copilots can pull live project intelligence straight into their workflows.<span className="ml-1.5 text-xs font-normal text-[var(--color-gray-400)]">(coming)</span></p>
              </div>
            </div>
          </div>
        </section>

        {/* CTA band */}
        <section className="bg-[var(--color-green)] py-16 text-center text-white">
          <div className="mx-auto max-w-2xl px-5">
            <h2 className="text-2xl font-bold">Build the category with us.</h2>
            <p className="mt-2 text-sm opacity-90">A handful of early access spots are open. See the projects you&apos;re missing this week.</p>
            <div className="mt-6 flex justify-center">
              <RequestDemoButton className="btn bg-white !text-[var(--color-green)] hover:opacity-90">
                Get early access &rarr;
              </RequestDemoButton>
            </div>
            <p className="mt-4 text-xs text-white/85">Founder-led &middot; Free during beta &middot; No plan room resale</p>
          </div>
        </section>

        <FAQ items={faqs} />
      </HomePageGate>
    </>
  );
}
