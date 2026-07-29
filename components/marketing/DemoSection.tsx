"use client";

// The lead-capture form itself now lives in DemoModal.tsx (a single shared
// modal, opened from any "Request Demo" trigger sitewide via useDemoModal())
// instead of this file's old DemoSection component, which was duplicated as
// a full-width section at the bottom of five separate pages.

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
