import Link from "next/link";
import { ProductMock } from "@/components/marketing/ProductMock";
import { StatsStrip, DemoSection } from "@/components/marketing/DemoSection";
import { FAQ } from "@/components/marketing/FAQ";
import { getProjects } from "@/lib/projects";

const faqs = [
  {
    q: "Do my reps need another dashboard?",
    a: "SpecIndex is built for quick search and visibility scans — not a heavy CRM replacement. Reps find open projects, check brand mentions, and export targets for outreach.",
  },
  {
    q: "How fast do we see Georgia projects?",
    a: "The public Georgia corpus is live today. We refresh from public sources weekly and can prioritize your product categories on request.",
  },
  {
    q: "What do you need to get started?",
    a: "Just your brand name and product categories. Full spec PDF analysis and alerts require a manufacturer account — we handle setup with your team.",
  },
  {
    q: "How is this different from Dodge or ConstructConnect?",
    a: "Those tools optimize for contractors and estimators. SpecIndex is built for manufacturers: brand mention detection, competitive visibility, and spec-stage opportunity scoring.",
  },
  {
    q: "Which states do you cover?",
    a: "Georgia is live now. Florida, North Carolina, South Carolina, and Tennessee are next on the roadmap.",
  },
];

export default function HomePage() {
  const count = getProjects().length;

  return (
    <>
      {/* Hero */}
      <section className="bg-[var(--color-bg)]">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 py-16 md:grid-cols-2 md:px-8 md:py-24">
          <div>
            <p className="text-eyebrow">For Building Product Manufacturers</p>
            <h1 className="mt-4 text-hero">
              Find the open projects where your brand can still win the spec.
            </h1>
            <p className="mt-5 max-w-lg text-base leading-relaxed text-[var(--color-gray-600)]">
              SpecIndex combines open commercial project data, specification
              intelligence, and brand visibility scoring to put your sales team
              in conversations before the window closes.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/projects/" className="btn btn-primary">
                Get a Demo
              </Link>
              <Link href="/visibility/" className="btn btn-outline">
                Check brand visibility
              </Link>
            </div>
            <p className="mt-6 text-sm text-[var(--color-gray-400)]">
              Built for manufacturer reps tracking commercial work in Georgia.
            </p>
          </div>
          <ProductMock />
        </div>
      </section>

      <StatsStrip
        stats={[
          { value: `${count}+`, label: "Open commercial projects indexed in Georgia" },
          { value: "All trades", label: "HVAC, glazing, flooring, MEP, and more" },
          { value: "Georgia", label: "Beachhead market — expanding statewide" },
          { value: "10+ layers", label: "Projects, specs, brands, teams, and sources" },
        ]}
      />

      {/* Problem */}
      <section className="bg-white">
        <div className="mx-auto max-w-3xl px-5 py-20 text-center md:px-8">
          <h2 className="text-section">
            There&apos;s an air gap between your reps and open project specs.
          </h2>
          <p className="mt-5 text-base leading-relaxed text-[var(--color-gray-600)]">
            Every week, commercial projects break ground, move to bidding, or publish
            updated plans across Georgia. Each one is a signal that someone will
            specify products — windows, HVAC, hardware, finishes.
          </p>
          <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
            Your CRM doesn&apos;t see any of it. Plan rooms bury the PDFs. And
            nobody on your team has time to manually check whether your brand is
            written in.
          </p>
        </div>
      </section>

      {/* Feature 1 */}
      <section className="border-t border-[var(--color-border)] bg-[var(--color-bg)]">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 py-20 md:grid-cols-2 md:px-8">
          <div>
            <p className="section-label">Out of the Box</p>
            <h2 className="text-section">Find open projects you didn&apos;t know existed.</h2>
            <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
              SpecIndex indexes open commercial work across Georgia — mixed-use,
              healthcare, industrial, hospitality — with status, value, teams, and
              manufacturer watch lists so reps know what&apos;s still in play.
            </p>
            <Link href="/projects/" className="mt-6 inline-block text-sm font-semibold text-[var(--color-green)] hover:underline">
              Search Georgia projects →
            </Link>
          </div>
          <div className="card p-5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
              Live Project Signal
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
                Brand check: Lutron mentioned on 0 of 20 Georgia projects. 8 projects
                watch lighting — opportunity list ready.
              </p>
              <p className="mt-2 text-[var(--color-gray-400)]">9:42 AM</p>
            </div>
          </div>
          <div className="order-1 md:order-2">
            <p className="section-label">Out of the Box</p>
            <h2 className="text-section">See if your brand is in — and where you&apos;re missing.</h2>
            <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
              Run a visibility scan against the Georgia corpus. See mention rate,
              category fit, and opportunity projects where your product area is in
              play but your brand isn&apos;t named yet.
            </p>
            <Link href="/visibility/" className="mt-6 inline-block text-sm font-semibold text-[var(--color-green)] hover:underline">
              Open visibility compare →
            </Link>
          </div>
        </div>
      </section>

      {/* Steps */}
      <section className="border-t border-[var(--color-border)] bg-[var(--color-gray-100)]">
        <div className="mx-auto max-w-6xl px-5 py-20 md:px-8">
          <h2 className="text-center text-section">From project signal to spec win in three steps.</h2>
          <ol className="mt-14 grid gap-10 md:grid-cols-3">
            {[
              {
                step: "Step 1",
                title: "SpecIndex watches your market.",
                body: "Public project data, permits, and coverage monitored across Georgia — filtered by trade and product category.",
              },
              {
                step: "Step 2",
                title: "You inspect specs and brand fit.",
                body: "Project detail pages show teams, key scopes, manufacturer watch lists, and whether your brand appears in public coverage.",
              },
              {
                step: "Step 3",
                title: "Your reps act.",
                body: "Prioritized project lists for outreach — who to call, why it matters, and what categories are still open.",
              },
            ].map((s) => (
              <li key={s.step}>
                <p className="font-mono text-xs font-semibold uppercase tracking-wider text-[var(--color-green)]">
                  {s.step}
                </p>
                <h3 className="mt-3 text-lg font-semibold">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--color-gray-600)]">
                  {s.body}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Comparison */}
      <section className="border-t border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-3xl px-5 py-20 text-center md:px-8">
          <h2 className="text-section">
            Your reps don&apos;t need another plan room to ignore.
          </h2>
          <div className="mt-10 space-y-4 text-left">
            {[
              ["Others give reps a map to explore.", "SpecIndex gives them projects still open for specs."],
              ["Others track what got built.", "SpecIndex finds what's about to be specified."],
              ["Others require digging through PDFs.", "SpecIndex surfaces brand mentions and watch lists."],
            ].map(([a, b]) => (
              <div
                key={a}
                className="grid gap-2 rounded-lg border border-[var(--color-border)] p-4 sm:grid-cols-2"
              >
                <p className="text-sm text-[var(--color-gray-600)]">{a}</p>
                <p className="text-sm font-semibold text-[var(--color-ink)]">{b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <FAQ items={faqs} />
      <DemoSection />
    </>
  );
}
