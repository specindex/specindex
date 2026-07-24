import Link from "next/link";

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

          <form className="card p-6 md:p-8">
            <h3 className="text-lg font-semibold">Request a Demo</h3>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <label className="block sm:col-span-1">
                <span className="text-xs font-medium text-[var(--color-gray-600)]">
                  First name
                </span>
                <input
                  required
                  className="mt-1.5 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </label>
              <label className="block sm:col-span-1">
                <span className="text-xs font-medium text-[var(--color-gray-600)]">
                  Last name
                </span>
                <input
                  required
                  className="mt-1.5 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="text-xs font-medium text-[var(--color-gray-600)]">
                  Work email
                </span>
                <input
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
                  required
                  className="mt-1.5 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="text-xs font-medium text-[var(--color-gray-600)]">
                  Product categories you sell
                </span>
                <input
                  placeholder="e.g. HVAC, glazing, flooring"
                  className="mt-1.5 w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--color-amber)] focus:ring-1 focus:ring-[var(--color-amber)]"
                />
              </label>
            </div>
            <Link href="/projects/" className="btn btn-primary mt-6 w-full">
              Get a Demo
            </Link>
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
