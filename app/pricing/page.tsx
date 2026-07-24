import type { Metadata } from "next";
import Link from "next/link";
import { DemoSection } from "@/components/marketing/DemoSection";

export const metadata: Metadata = {
  title: "Pricing",
  description: "SpecIndex pricing for building product manufacturers.",
};

const plans = [
  {
    name: "Free",
    price: "$0",
    period: "Georgia browse",
    description: "Explore the public Georgia corpus and run limited brand checks.",
    features: [
      "Browse open Georgia projects",
      "Project search and filters",
      "1 brand visibility scan / week",
      "Public source attribution",
    ],
    cta: "Browse projects",
    href: "/projects/",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "Contact us",
    period: "per seat / month",
    description: "Unlimited search and visibility for manufacturer reps in Georgia.",
    features: [
      "Unlimited Georgia project search",
      "Unlimited brand visibility scans",
      "Competitor compare (up to 5 brands)",
      "Category opportunity lists",
      "Email alerts (weekly digest)",
    ],
    cta: "Get a Demo",
    href: "/#demo",
    highlighted: true,
  },
  {
    name: "Team",
    price: "Contact us",
    period: "multi-seat",
    description: "For rep firms and enterprise manufacturers with multi-brand books.",
    features: [
      "Everything in Pro",
      "Multi-brand profiles",
      "Territory seats and exports",
      "Spec PDF upload + NER (beta)",
      "CRM export / API (roadmap)",
      "Southeast expansion priority",
    ],
    cta: "Talk to us",
    href: "mailto:hello@specindex.ai?subject=SpecIndex%20Team%20plan",
    highlighted: false,
  },
];

export default function PricingPage() {
  return (
    <>
      <section className="border-b border-[var(--color-border)] bg-[var(--color-bg)]">
        <div className="mx-auto max-w-3xl px-5 py-16 text-center md:px-8 md:py-20">
          <p className="text-eyebrow">Pricing</p>
          <h1 className="mt-4 text-hero">Start free in Georgia. Scale with your territory.</h1>
          <p className="mt-5 text-base leading-relaxed text-[var(--color-gray-600)]">
            Public project browse is free. Manufacturer intelligence — brand alerts,
            competitive compare, spec analysis — on paid seats.
          </p>
        </div>
      </section>

      <section className="bg-white">
        <div className="mx-auto grid max-w-6xl gap-6 px-5 py-16 md:grid-cols-3 md:px-8">
          {plans.map((plan) => (
            <article
              key={plan.name}
              className={`card flex flex-col p-6 md:p-8 ${
                plan.highlighted
                  ? "border-[var(--color-amber)] ring-2 ring-[var(--color-amber)]/30"
                  : ""
              }`}
            >
              {plan.highlighted && (
                <span className="pill mb-4 w-fit">Most popular</span>
              )}
              <h2 className="text-lg font-semibold">{plan.name}</h2>
              <p className="mt-2 text-3xl font-bold">{plan.price}</p>
              <p className="text-sm text-[var(--color-gray-400)]">{plan.period}</p>
              <p className="mt-4 text-sm leading-relaxed text-[var(--color-gray-600)]">
                {plan.description}
              </p>
              <ul className="mt-6 flex-1 space-y-2.5">
                {plan.features.map((f) => (
                  <li
                    key={f}
                    className="flex gap-2 text-sm text-[var(--color-gray-600)]"
                  >
                    <span className="text-[var(--color-green)]">+</span>
                    {f}
                  </li>
                ))}
              </ul>
              <Link
                href={plan.href}
                className={`mt-8 w-full text-center ${plan.highlighted ? "btn btn-primary" : "btn btn-outline"}`}
              >
                {plan.cta}
              </Link>
            </article>
          ))}
        </div>
      </section>

      <DemoSection />
    </>
  );
}
