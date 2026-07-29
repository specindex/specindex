import type { Metadata } from "next";
import { VisibilityPanel } from "@/components/VisibilityPanel";
import { getSampleProjects } from "@/lib/projects";

export const metadata: Metadata = {
  title: "Brand Visibility",
  description:
    "Check how often your brand appears across commercial projects nationwide, and find the projects where your category is still open.",
};

export default async function VisibilityPage() {
  // getProjects() fetched the ENTIRE corpus (~175K+ rows, headed to 6.5M+)
  // and embedded it as a prop into this page's client bundle -- timed out
  // the build the same way /projects/[id] did (docs/ROADMAP.md item 44's
  // follow-up), and would've been a multi-MB payload even if it hadn't.
  // Bounded to a representative top-scored sample as a stopgap; the real
  // fix is VisibilityPanel fetching/paginating client-side against the API
  // the way components/ProjectsDashboard.tsx already does, instead of
  // receiving the whole corpus as a prop.
  const projects = await getSampleProjects(2000);

  return (
    <div className="bg-[var(--color-bg)]">
      <div className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl px-5 py-12 md:px-8 md:py-16">
          <p className="text-eyebrow">Brand intelligence</p>
          <h1 className="mt-3 text-hero">Brand check</h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--color-gray-600)]">
            Enter a brand and a category to see where it already appears across the
            index, and which projects need that category without naming a
            manufacturer.
          </p>
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <VisibilityPanel projects={projects} />
      </div>
    </div>
  );
}
