import type { Metadata } from "next";
import { ProjectsDashboard } from "@/components/ProjectsDashboard";
import { getStats } from "@/lib/projects";

export const metadata: Metadata = {
  title: "Projects",
  description:
    "Search open commercial construction projects across the United States. Filter by state, county, status, and product category.",
};

export default async function ProjectsPage() {
  const stats = await getStats();

  return (
    <div className="bg-[var(--color-bg)]">
      <div className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl px-5 py-12 md:px-8 md:py-16">
          <p className="text-eyebrow">United States</p>
          <h1 className="mt-3 text-hero">Projects worth chasing this week</h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--color-gray-600)]">
            Ranked by priority score, filtered to your territory and product category —
            not a browse-everything list. {stats.total.toLocaleString()}+ projects indexed across{" "}
            {stats.states} states, {stats.early_stage.toLocaleString()}+ still in early stage
            (planning through bidding), if you want to search the full corpus.
          </p>
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <ProjectsDashboard />
      </div>
    </div>
  );
}
