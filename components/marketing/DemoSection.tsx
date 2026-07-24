"use client";

import Link from "next/link";
import { useState } from "react";

type Stat = { value: string; label: string };

export function StatsStrip({ stats }: { stats: Stat[] }) {
  return (
    <section className="border-y border-[var(--color-border)] bg-white">
      <div className="mx-auto grid max-w-6xl divide-y divide-[var(--color-border)] sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="px-5 py-10 text-center md:px-8">
            <p className="text-stat">{s.value}</p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--color-gray-600)]">
              {s.label}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

export function DemoSection() {
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const first = String(data.get("firstName") ?? "");
    const last = String(data.get("lastName") ?? "");
    const email = String(data.get("email") ?? "");
    const company = String(data.get("company") ?? "");
    const categories = String(data.get("categories") ?? "");

    const subject = encodeURIComponent(`SpecIndex demo request — ${company}`);
    const body = encodeURIComponent(
      [
        "Demo request from specindex.ai",
        "",
        `Name: ${first} ${last}`,
        `Email: ${email}`,
        `Company: ${company}`,
        `Product categories: ${categories || "Not specified"}`,
      ].join("\n"),
    );

    window.location.href = `mailto:hello@specindex.ai?subject=${subject}&body=${body}`;
    setSubmitted(true);
  }

  return (
    <section id="demo" className="border-t border-[var(--color-border)] bg-[var(--color-gray-100)]">
      <div className="mx-auto max-w-6xl px-5 py-20 md:px-8">
        <div className="grid gap-12 lg:grid-cols-2 lg:items-start">
          <div>
            <h2 className="text-section">Never miss another spec window.</h2>
            <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
              See the open commercial projects in Georgia where your brand can still
              win — and how you compare to competitors in the same categories.
            </p>
            <p className="mt-3 text-sm text-[var(--color-gray-600)]">
              Fill out the form and we&apos;ll show you real projects in your market
              within one business day.
            </p>
          </div>

          <form className="card p-6 md:p-8" onSubmit={handleSubmit}>
            <h3 className="text-lg font-semibold">Request a Demo</h3>
            {submitted ? (
              <p className="mt-4 rounded-md bg-[var(--color-green-light)] px-4 py-3 text-sm text-[var(--color-green)]">
                Thanks — your email client should open with a pre-filled message. Send
                it to complete your request, or email us at{" "}
                <a href="mailto:hello@specindex.ai" className="underline">
                  hello@specindex.ai
                </a>
                .
              </p>
            ) : null}
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <label className="block sm:col-span-1">
                <span className="text-xs font-medium text-[var(--color-gray-600)]">
                  First name
                </span>
                <input
                  name="firstName"
                  required
                  className="mt-1.5 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </label>
              <label className="block sm:col-span-1">
                <span className="text-xs font-medium text-[var(--color-gray-600)]">
                  Last name
                </span>
                <input
                  name="lastName"
                  required
                  className="mt-1.5 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="text-xs font-medium text-[var(--color-gray-600)]">
                  Work email
                </span>
                <input
                  name="email"
                  type="email"
                  required
                  className="mt-1.5 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="text-xs font-medium text-[var(--color-gray-600)]">
                  Company
                </span>
                <input
                  name="company"
                  required
                  className="mt-1.5 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="text-xs font-medium text-[var(--color-gray-600)]">
                  Product categories you sell
                </span>
                <input
                  name="categories"
                  placeholder="e.g. HVAC, glazing, flooring"
                  className="mt-1.5 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </label>
            </div>
            <button type="submit" className="btn btn-primary mt-6 w-full">
              Request Demo
            </button>
            <p className="mt-3 text-center text-xs text-[var(--color-gray-400)]">
              Or browse the{" "}
              <Link href="/projects/" className="underline hover:text-[var(--color-ink)]">
                Georgia project index
              </Link>{" "}
              now.
            </p>
          </form>
        </div>
      </div>
    </section>
  );
}
