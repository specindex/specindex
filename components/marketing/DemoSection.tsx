"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

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
  const pathname = usePathname();
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    setPending(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/v1/contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: String(data.get("firstName") ?? ""),
          last_name: String(data.get("lastName") ?? ""),
          email: String(data.get("email") ?? ""),
          company: String(data.get("company") ?? ""),
          categories: String(data.get("categories") ?? ""),
          source_path: pathname,
        }),
      });
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      form.reset();
      setSubmitted(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message} — email us directly at hello@specindex.ai instead.`
          : "Something went wrong — email us directly at hello@specindex.ai instead."
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <section id="demo" className="border-t border-[var(--color-border)] bg-[var(--color-gray-100)]">
      <div className="mx-auto max-w-6xl px-5 py-20 md:px-8">
        <div className="grid gap-12 lg:grid-cols-2 lg:items-start">
          <div>
            <h2 className="text-section">See what is still open in your territory.</h2>
            <p className="mt-4 text-base leading-relaxed text-[var(--color-gray-600)]">
              Tell us your brand and the divisions you sell. We come back with the
              projects in your markets where the product decision is still live, plus
              the ones where a competitor already has their name on it.
            </p>
            <p className="mt-3 text-sm text-[var(--color-gray-600)]">
              Real projects from the index, within one business day.
            </p>
          </div>

          <form className="card p-6 md:p-8" onSubmit={handleSubmit}>
            <h3 className="text-lg font-semibold">Request a Demo</h3>
            {submitted ? (
              <p className="mt-4 rounded-md bg-[var(--color-green-light)] px-4 py-3 text-sm text-[var(--color-green)]">
                Thanks — we&apos;ve got your request and will follow up within one
                business day. You can also write to us directly at{" "}
                <a href="mailto:hello@specindex.ai" className="underline">
                  hello@specindex.ai
                </a>
                .
              </p>
            ) : null}
            {error ? (
              <p className="mt-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>
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
            <button type="submit" disabled={pending} className="btn btn-primary mt-6 w-full disabled:opacity-60">
              {pending ? "Sending…" : "Request Demo"}
            </button>
            <p className="mt-3 text-center text-xs text-[var(--color-gray-400)]">
              Or{" "}
              <Link href="/projects/" className="underline hover:text-[var(--color-ink)]">
                search the index
              </Link>{" "}
              first. No account needed.
            </p>
          </form>
        </div>
      </div>
    </section>
  );
}
