import type { Metadata } from "next";
import Link from "next/link";
import { DemoSection } from "@/components/marketing/DemoSection";

export const metadata: Metadata = {
  title: "Product",
  description: "SpecIndex use cases for building product manufacturers.",
};

const useCases = [
  {
    label: "Out of the Box",
    title: "Search open commercial projects",
    body: "Filter Georgia projects by status, type, county, and product category. See what's still open for manufacturer influence — planning through under construction.",
    href: "/projects/",
    cta: "Browse Georgia projects",
  },
  {
    label: "Out of the Box",
    title: "Read project specs and teams",
    body: "Project pages consolidate owner, architect, GC, key scopes, manufacturer watch lists, and sources — so reps don't chase plan rooms for basics.",
    href: "/projects/georgia-pacific-center-conversion/",
    cta: "View sample project",
  },
  {
    label: "Out of the Box",
    title: "Check brand visibility",
    body: "Scan the corpus for your brand mentions vs category opportunities. See mention rate and a prioritized list of projects where your product area is in play but you're not named.",
    href: "/visibility/",
    cta: "Run visibility scan",
  },
  {
    label: "With Your Data",
    title: "Spec PDF analysis and alerts",
    body: "Upload or connect spec documents for AI extraction, brand NER with confidence scores, and email alerts when your brand appears or disappears on a tracked project.",
    href: "/pricing/",
    cta: "See pricing",
  },
  {
    label: "With Your Data",
    title: "Competitive share by market",
    body: "Track mention rate vs named competitors by county, project type, and CSI division — the manufacturer equivalent of share-of-spec reporting.",
    href: "/pricing/",
    cta: "Talk to us",
  },
];

export default function ProductPage() {
  return (
    <>
      <section className="border-b border-[var(--color-border)] bg-[var(--color-bg)]">
        <div className="mx-auto max-w-3xl px-5 py-16 text-center md:px-8 md:py-20">
          <p className="text-eyebrow">Product</p>
          <h1 className="mt-4 text-hero">Specification intelligence built for manufacturers.</h1>
          <p className="mt-5 text-base leading-relaxed text-[var(--color-gray-600)]">
            Strong on day one with public Georgia project data. Unmatched when you
            connect specs, brands, and territory rules.
          </p>
        </div>
      </section>

      <section className="bg-white">
        <div className="mx-auto max-w-6xl px-5 py-16 md:px-8">
          <div className="grid gap-8 md:grid-cols-2">
            {useCases.map((uc) => (
              <article key={uc.title} className="card p-6 md:p-8">
                <p className="section-label">{uc.label}</p>
                <h2 className="text-xl font-semibold">{uc.title}</h2>
                <p className="mt-3 text-sm leading-relaxed text-[var(--color-gray-600)]">
                  {uc.body}
                </p>
                <Link
                  href={uc.href}
                  className="mt-5 inline-block text-sm font-semibold text-[var(--color-green)] hover:underline"
                >
                  {uc.cta} →
                </Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <DemoSection />
    </>
  );
}
