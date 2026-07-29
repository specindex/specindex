import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Product",
  description: "SpecIndex use cases for building product manufacturers.",
};

const useCases = [
  {
    label: "Available now",
    title: "Search the project index",
    body: "Filter commercial projects by state, county, stage, project type, and product category. Planning through under construction, so you can tell an early conversation from a late one.",
    href: "/projects/",
    cta: "Search the index",
  },
  {
    label: "Available now",
    title: "Read the project record",
    body: "One page per project: owner, architect, contractor, value, square footage, the scopes that matter, the categories still in play, and links to every source behind it.",
    href: "/projects/ga-georgia-pacific-center-conversion/",
    cta: "View a sample record",
  },
  {
    label: "Available now",
    title: "Check your brand against the index",
    body: "See how often your brand appears, which projects name your category without naming a manufacturer, and which of your competitors show up instead.",
    href: "/visibility/",
    cta: "Run a brand check",
  },
  {
    label: "In development",
    title: "Specification-book reading",
    body: "Full specification books, read cover to cover, with every fact traceable to the page it came from.",
    href: "/pricing/",
    cta: "See pricing",
  },
  {
    label: "In development",
    title: "Share of spec by market",
    body: "How often you appear against named competitors, broken out by county, project type, and CSI division. It is the closest thing a manufacturer gets to a market share report.",
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
          <h1 className="mt-4 text-hero">Built around one question: is my category still open?</h1>
          <p className="mt-5 text-base leading-relaxed text-[var(--color-gray-600)]">
            Everything below is either working in the index today or labelled as
            still being built. Nothing in between.
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
    </>
  );
}
