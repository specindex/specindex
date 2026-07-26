import type { Metadata } from "next";
import Link from "next/link";
import { DemoSection } from "@/components/marketing/DemoSection";
import { StatsStrip } from "@/components/marketing/DemoSection";
import { getProjects } from "@/lib/projects";

export const metadata: Metadata = {
  title: "About",
  description:
    "Why SpecIndex exists: specification intelligence for building product manufacturers.",
};

export default async function AboutPage() {
  const count = (await getProjects()).length;

  return (
    <>
      <section className="border-b border-[var(--color-border)] bg-[var(--color-bg)]">
        <div className="mx-auto max-w-3xl px-5 py-16 md:px-8 md:py-20">
          <p className="text-eyebrow">About</p>
          <h1 className="mt-4 text-hero">
            Specification intelligence for building product manufacturers.
          </h1>
          <p className="mt-6 text-base leading-relaxed text-[var(--color-gray-600)]">
            Whether a building product gets bought is settled by an architect or an
            engineer, written into a document, and finished months before anyone asks
            for a quote. The manufacturer usually finds out well after the fact.
          </p>
          <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
            Most of that process leaves a public trail. We read it, turn it into
            something searchable, and keep the citation attached, so a rep can see how
            far along a job is, which categories nobody has committed to yet, and who
            has already been named.
          </p>
        </div>
      </section>

      <StatsStrip
        stats={[
          { value: `${count}+`, label: "Commercial projects in the live index" },
          { value: "50", label: "States covered" },
          { value: "Public", label: "Only source of project data we use" },
          { value: "2026", label: "Year SpecIndex launched" },
        ]}
      />

      <section className="bg-white">
        <div className="mx-auto max-w-3xl px-5 py-16 md:px-8">
          <h2 className="text-section">What we&apos;re building</h2>
          <ul className="mt-8 space-y-4 text-base leading-relaxed text-[var(--color-gray-600)]">
            <li>
              <strong className="text-[var(--color-ink)]">The index.</strong> Commercial
              projects across the country, filtered by state, county, stage and CSI
              division.
            </li>
            <li>
              <strong className="text-[var(--color-ink)]">The project record.</strong>{" "}
              Team, scopes, categories in play and every source, on one page.
            </li>
            <li>
              <strong className="text-[var(--color-ink)]">Brand visibility.</strong>{" "}
              Where your name shows up, where a competitor&apos;s does, and where
              nobody has been named.
            </li>
            <li>
              <strong className="text-[var(--color-ink)]">Specification extraction.</strong>{" "}
              Spec books read division by division, with every fact traceable to its
              page. Still being built.
            </li>
          </ul>
          <div className="mt-10 flex flex-wrap gap-3">
            <Link href="#demo" className="btn btn-primary">
              Request Demo
            </Link>
            <Link href="/projects/" className="btn btn-outline">
              Search the index
            </Link>
          </div>
        </div>
      </section>

      <DemoSection />
    </>
  );
}
