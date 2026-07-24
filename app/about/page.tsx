import type { Metadata } from "next";
import Link from "next/link";
import { DemoSection } from "@/components/marketing/DemoSection";
import { StatsStrip } from "@/components/marketing/DemoSection";
import { getProjects } from "@/lib/projects";

export const metadata: Metadata = {
  title: "About",
  description: "About SpecIndex — specification intelligence for building product manufacturers.",
};

export default function AboutPage() {
  const count = getProjects().length;

  return (
    <>
      <section className="border-b border-[var(--color-border)] bg-[var(--color-bg)]">
        <div className="mx-auto max-w-3xl px-5 py-16 md:px-8 md:py-20">
          <p className="text-eyebrow">About</p>
          <h1 className="mt-4 text-hero">
            Specification intelligence for building product manufacturers.
          </h1>
          <p className="mt-6 text-base leading-relaxed text-[var(--color-gray-600)]">
            SpecIndex helps manufacturers search open commercial projects, inspect
            project specs, detect whether their brand is mentioned, and compare
            visibility inside a market — starting with Georgia.
          </p>
          <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
            Plan rooms and bid boards are built for contractors. SpecIndex is built
            for the rep who needs to know: Is this project still open? Is my brand
            in the spec? Who do I call before the window closes?
          </p>
        </div>
      </section>

      <StatsStrip
        stats={[
          { value: `${count}+`, label: "Georgia projects in the live corpus" },
          { value: "2026", label: "Beachhead launch year" },
          { value: "GA → SE", label: "Expansion roadmap" },
          { value: "Manufacturers", label: "Primary buyer persona" },
        ]}
      />

      <section className="bg-white">
        <div className="mx-auto max-w-3xl px-5 py-16 md:px-8">
          <h2 className="text-section">What we&apos;re building</h2>
          <ul className="mt-8 space-y-4 text-base leading-relaxed text-[var(--color-gray-600)]">
            <li>
              <strong className="text-[var(--color-ink)]">Project search</strong> —
              open commercial work filtered by stage, type, and product category.
            </li>
            <li>
              <strong className="text-[var(--color-ink)]">Spec detail</strong> —
              teams, scopes, watch lists, and sources on one page.
            </li>
            <li>
              <strong className="text-[var(--color-ink)]">Brand visibility</strong> —
              mention detection and competitive compare across a market.
            </li>
            <li>
              <strong className="text-[var(--color-ink)]">Alerts &amp; NER</strong> —
              spec PDF analysis and notifications (Team tier, rolling out).
            </li>
          </ul>
          <div className="mt-10 flex flex-wrap gap-3">
            <Link href="/#demo" className="btn btn-primary">
              Request Demo
            </Link>
            <Link href="/projects/" className="btn btn-outline">
              Browse Georgia projects
            </Link>
          </div>
        </div>
      </section>

      <DemoSection />
    </>
  );
}
