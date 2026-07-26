import type { Metadata } from "next";
import { CoverageTable } from "@/components/CoverageTable";
import { getCoverage } from "@/lib/coverage";

export const metadata: Metadata = {
  title: "Data Coverage",
  robots: { index: false, follow: false },
};

export default async function CoveragePage() {
  const coverage = await getCoverage();

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
            <code>scripts/compute-county-coverage.py</code> after a corpus reload.
          </p>
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <CoverageTable coverage={coverage} />
      </div>
    </div>
  );
}
