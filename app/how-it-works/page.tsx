import type { Metadata } from "next";
import Link from "next/link";
import { DemoSection } from "@/components/marketing/DemoSection";

export const metadata: Metadata = {
  title: "How It Works",
  description:
    "How SpecIndex turns public permit filings and project announcements into structured, citable project records.",
};

const steps = [
  {
    step: "01",
    title: "We read the public record",
    body: "County and city permit filings, state economic development announcements, owner and developer releases, and construction trade press, across all 50 states.",
    detail: "Some counties publish permits as open data, which is where coverage is deepest. Elsewhere we work from announcements and trade coverage.",
  },
  {
    step: "02",
    title: "Each project becomes a structured record",
    body: "Loose filing text and press copy get turned into the same set of fields every time: stage, location, value, square footage, owner, architect, contractor, and what the job will need.",
    detail: "Every record keeps links to the sources behind it, so you can check our work.",
  },
  {
    step: "03",
    title: "You filter down to what you sell",
    body: "State, county, stage, project type, and CSI division. A job still in design is a different conversation from one already framed, so the stage sits on every record.",
    detail: "No login and no plan room subscription for the public index.",
  },
  {
    step: "04",
    title: "You check your brand against it",
    body: "Enter your brand and category to see how many projects need what you sell, how many are still early, and how many name a manufacturer at all.",
    detail: "Reading spec books, with a citation on every extracted fact, is the next layer being built.",
  },
];

export default function HowItWorksPage() {
  return (
    <>
      <section className="border-b border-[var(--color-border)] bg-[var(--color-bg)]">
        <div className="mx-auto max-w-3xl px-5 py-16 text-center md:px-8 md:py-20">
          <p className="text-eyebrow">How It Works</p>
          <h1 className="mt-4 text-hero">Public filings in. Structured projects out.</h1>
          <p className="mt-5 text-base leading-relaxed text-[var(--color-gray-600)]">
            There is no private feed behind SpecIndex. Everything in the index comes
            from records anyone is allowed to read. The effort goes into finding them,
            reading them the same way every time, and keeping the citation attached.
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
          <h2 className="text-section">Want this run against your territory?</h2>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="#demo" className="btn btn-primary">
              Request Demo
            </Link>
            <Link href="/projects/" className="btn btn-outline">
              Search the index
            </Link>
            <Link href="/visibility/" className="btn btn-outline">
              Run a brand check
            </Link>
          </div>
        </div>
      </section>

      <DemoSection />
    </>
  );
}
