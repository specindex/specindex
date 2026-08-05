import type { Metadata } from "next";
import { ProjectsDashboard } from "@/components/ProjectsDashboard";
import { ProjectsGate } from "@/components/ProjectsGate";
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
          {/* No raw six-digit counts. This headline read "591,618+ projects
              indexed across 50 states, 577,827+ still in early stage" -- two
              exact live counts that go stale weekly, contradict the 500K+
              figure used in every other SpecIndex material, and invite the one
              comparison this product loses (ConstructConnect claims 825,000).
              The counter under the filters was fixed earlier; this headline
              above them was missed.

              "Ranked by priority score" is also dropped: it was true of the
              sort and misleading about the corpus, since spec position -- 45
              of the 100 points -- currently fires on 0.3% of projects. The
              honest claim is the window, not the ranking. */}
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--color-gray-600)]">
            Filtered to your territory and product category — not a
            browse-everything list. 500K+ commercial projects across{" "}
            {stats.states} states, 97% still early stage (planning through
            bidding), every one traceable to a public source.
          </p>
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <ProjectsGate>
          <ProjectsDashboard />
        </ProjectsGate>
      </div>
    </div>
  );
}
