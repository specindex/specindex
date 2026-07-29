import type { Metadata } from "next";
import Link from "next/link";
import { RequestDemoButton } from "@/components/marketing/RequestDemoButton";

export const metadata: Metadata = {
  title: "Pricing",
  description: "SpecIndex pricing for building product manufacturers.",
};

const plans = [
  {
    name: "Free",
    price: "$0",
    period: "public index",
    description: "Search the public index and run a brand check now and then.",
    features: [
      "Search commercial projects in all 50 states",
      "Filter by state, county, stage, and category",
      "1 brand check per week",
      "Source links on every project",
    ],
    cta: "Search the index",
    href: "/projects/",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "Contact us",
    period: "per seat / month",
    description: "For reps working a territory who need this every morning.",
    features: [
      "Unlimited search across the national index",
      "Unlimited brand checks",
      "Competitor compare (up to 5 brands)",
      "Lists of projects with your category still open",
      "Weekly email digest for your territory",
    ],
    cta: "Request Demo",
    href: "#demo",
    highlighted: true,
  },
  {
    name: "Team",
    price: "Contact us",
    period: "multi-seat",
    description: "For rep firms and manufacturers carrying several brands at once.",
    features: [
      "Everything in Pro",
      "Multiple brand profiles",
      "Territory seats and list exports",
      "Spec book upload and extraction (beta)",
      "CRM export and API (roadmap)",
      "Priority on the jurisdictions you care about",
    ],
    cta: "Talk to us",
    href: "#demo",
    highlighted: false,
  },
];

export default function PricingPage() {
  return (
    <>
      <section className="border-b border-[var(--color-border)] bg-[var(--color-bg)]">
        <div className="mx-auto max-w-3xl px-5 py-16 text-center md:px-8 md:py-20">
          <p className="text-eyebrow">Pricing</p>
          <h1 className="mt-4 text-hero">The index is free to search. Always.</h1>
          <p className="mt-5 text-base leading-relaxed text-[var(--color-gray-600)]">
            Anyone can search public project data without paying us for it. The paid
            seats cover the work layered on top: brand tracking, competitor compare,
            alerts, and reading the spec books.
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
              {plan.href === "#demo" ? (
                <RequestDemoButton
                  className={`mt-8 w-full text-center ${plan.highlighted ? "btn btn-primary" : "btn btn-outline"}`}
                >
                  {plan.cta}
                </RequestDemoButton>
              ) : (
                <Link
                  href={plan.href}
                  className={`mt-8 w-full text-center ${plan.highlighted ? "btn btn-primary" : "btn btn-outline"}`}
                >
                  {plan.cta}
                </Link>
              )}
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
