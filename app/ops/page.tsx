import type { Metadata } from "next";
import { OpsDashboard } from "@/components/OpsDashboard";

export const metadata: Metadata = {
  title: "Ops",
  robots: { index: false, follow: false },
};

export default function OpsPage() {
  return (
    <div className="bg-[var(--color-bg)]">
      <div className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl px-5 py-12 md:px-8 md:py-16">
          <p className="text-eyebrow">Internal</p>
          <h1 className="mt-3 text-hero">Ops dashboard</h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--color-gray-600)]">
            Live system status: API/database health, pipeline run history (agents
            pulling/loading/refreshing coverage), data staleness, and known
            infrastructure costs. Fetched live from the browser, not baked in at build
            time, since freshness matters more than build-time SEO for this page. Not
            linked from public nav; a real login-gated admin portal is planned.
          </p>
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <OpsDashboard />
      </div>
    </div>
  );
}
