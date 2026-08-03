import type { Metadata } from "next";
import { CoverageTabs } from "@/components/CoverageTabs";
import { getCoverage, getCoverageInsights, getQuality, getTop500 } from "@/lib/coverage";

export const metadata: Metadata = {
  title: "Data Coverage",
  robots: { index: false, follow: false },
};

export default async function CoveragePage() {
  const [coverage, insights, quality, top500] = await Promise.all([
    getCoverage(),
    getCoverageInsights(),
    getQuality(),
    getTop500(),
  ]);

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
          <p className="mt-3 max-w-2xl text-base leading-relaxed text-[var(--color-gray-600)]">
            The <strong>Top 500 Counties</strong> tab measures the same corpus against
            the Census population ranking, so it also shows the large counties where we
            hold <em>nothing</em> — those never appear in a table built from what we
            already have. It counts both projects and documents, because breadth without
            documents is only a partial win. Refresh with{" "}
            <code>scripts/compute-top500-coverage.py</code>.
          </p>
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <CoverageTabs
          coverage={coverage}
          insights={insights}
          quality={quality}
          top500={top500}
        />
      </div>
    </div>
  );
}
