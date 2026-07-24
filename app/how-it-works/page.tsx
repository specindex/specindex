import type { Metadata } from "next";
import Link from "next/link";
import { DemoSection } from "@/components/marketing/DemoSection";

export const metadata: Metadata = {
  title: "How It Works",
  description: "How SpecIndex turns open project signals into manufacturer action.",
};

const steps = [
  {
    step: "01",
    title: "SpecIndex captures open projects",
    body: "We aggregate public commercial project coverage across Georgia — announcements, groundbreakings, permits, and owner releases — and structure them for search.",
    detail: "Projects include status, value, teams, key specs, manufacturer watch lists, and source links.",
  },
  {
    step: "02",
    title: "You search, filter, and inspect",
    body: "Reps filter by city, project type, status, and product category. Project detail pages show what's specified, who's on the team, and what's still open for influence.",
    detail: "No plan room login required for the public Georgia corpus.",
  },
  {
    step: "03",
    title: "Brand visibility scoring",
    body: "Enter your brand and product categories. SpecIndex calculates mention rate across the corpus and surfaces opportunity projects — category fit without a brand hit.",
    detail: "Phase 2 adds spec PDF NER, excerpts, and confidence scores.",
  },
  {
    step: "04",
    title: "Reps prioritize outreach",
    body: "Export target lists, share project links with distributors, and align territory coverage to open work still in spec or bidding windows.",
    detail: "Alerts and CRM sync available on Team plans.",
  },
];

export default function HowItWorksPage() {
  return (
    <>
      <section className="border-b border-[var(--color-border)] bg-[var(--color-bg)]">
        <div className="mx-auto max-w-3xl px-5 py-16 text-center md:px-8 md:py-20">
          <p className="text-eyebrow">How It Works</p>
          <h1 className="mt-4 text-hero">From signal to spec win in four steps.</h1>
          <p className="mt-5 text-base leading-relaxed text-[var(--color-gray-600)]">
            SpecIndex is the system of action that tells your team which Georgia
            projects to pursue — before specs lock.
          </p>
        </div>
      </section>

      <section className="bg-white">
        <ol className="mx-auto max-w-3xl divide-y divide-[var(--color-border)] px-5 md:px-8">
          {steps.map((s) => (
            <li key={s.step} className="py-12">
              <p className="font-mono text-sm font-semibold text-[var(--color-green)]">
                {s.step}
              </p>
              <h2 className="mt-2 text-xl font-semibold">{s.title}</h2>
              <p className="mt-3 text-base leading-relaxed text-[var(--color-gray-600)]">
                {s.body}
              </p>
              <p className="mt-2 text-sm text-[var(--color-gray-400)]">{s.detail}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-t border-[var(--color-border)] bg-[var(--color-gray-100)]">
        <div className="mx-auto max-w-3xl px-5 py-16 text-center md:px-8">
          <h2 className="text-section">Ready to see it on your territory?</h2>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="/projects/" className="btn btn-primary">
              Browse Georgia projects
            </Link>
            <Link href="/visibility/" className="btn btn-outline">
              Check brand visibility
            </Link>
          </div>
        </div>
      </section>

      <DemoSection />
    </>
  );
}
