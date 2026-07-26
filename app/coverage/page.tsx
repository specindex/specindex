import type { Metadata } from "next";
import { CoverageTabs } from "@/components/CoverageTabs";
import { getCoverage, getCoverageInsights } from "@/lib/coverage";

export const metadata: Metadata = {
  title: "Data Coverage",
  robots: { index: false, follow: false },
};

export default async function CoveragePage() {
  const [coverage, insights] = await Promise.all([getCoverage(), getCoverageInsights()]);

  return (
    <div className="bg-[var(--color-bg)]">
      <div className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl px-5 py-12 md:px-8 md:py-16">
          <p className="text-eyebrow">Internal</p>
          <h1 className="mt-3 text-hero">Data coverage by county</h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--color-gray-600)]">
            Which counties have a project in the corpus, how many, which source(s)
            contributed them, and whether that county has a dedicated local permit
            feed (&ldquo;deep&rdquo;) or only broad statewide/federal coverage
            (&ldquo;thin&rdquo;). Backed by the <code>county_coverage</code> table in
            Cloud SQL — refresh it with{" "}
            <code>scripts/compute-county-coverage.py</code> after a corpus reload. This
            is the dashboard for deciding where to point the next pull script — the
            goal is closing the gap on uncovered counties, one verified source at a time.
          </p>
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <CoverageTabs coverage={coverage} insights={insights} />
      </div>
    </div>
  );
}
