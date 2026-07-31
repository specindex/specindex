import type { Metadata } from "next";
import Link from "next/link";
import { RequestDemoButton } from "@/components/marketing/RequestDemoButton";

export const metadata: Metadata = {
  title: "How It Works",
  description:
    "Commercial projects in all 50 states, filterable by state and county.",
};

const steps = [
  {
    step: "01",
    title: "An extensive, growing database",
    body: "Commercial projects across all 50 states, added continuously as new ones come up — nothing licensed, nothing pulled from a paid plan room.",
    detail: "Coverage depth varies by market.",
  },
  {
    step: "02",
    title: "Each project becomes a structured record",
    body: "Every project carries the same fields: stage, location, value, square footage, owner, architect, contractor, and what the job will need.",
    detail: "Every record keeps links to the sources behind it, so you can check our work.",
  },
  {
    step: "03",
    title: "You filter down to what you sell",
    body: "State, county, stage, project type, and CSI division. A job still in design is a different conversation from one already framed, so the stage sits on every record.",
    detail: "No plan room subscription required.",
  },
  {
    step: "04",
    title: "You check your brand against it",
    body: "Enter your brand and category to see how many projects need what you sell, how many are still early, and how many name a manufacturer at all.",
    detail: "Reading full specification books is the next layer being built.",
  },
];

export default function HowItWorksPage() {
  return (
    <>
      <section className="border-b border-[var(--color-border)] bg-[var(--color-bg)]">
        <div className="mx-auto max-w-3xl px-5 py-16 text-center md:px-8 md:py-20">
          <p className="text-eyebrow">How It Works</p>
          <h1 className="mt-4 text-hero">An extensive database of commercial projects, structured and ranked.</h1>
          <p className="mt-5 text-base leading-relaxed text-[var(--color-gray-600)]">
            SpecIndex maintains a continuously growing database of commercial
            construction projects nationwide, with a source link kept on every
            project so you can verify it yourself.
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
            <RequestDemoButton className="btn btn-demo" />
            <Link href="/projects/" className="btn btn-outline">
              Search the index
            </Link>
            <Link href="/visibility/" className="btn btn-outline">
              Run a brand check
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
