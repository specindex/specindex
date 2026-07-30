import type { Metadata } from "next";
import { VisibilityPanel } from "@/components/VisibilityPanel";
import { ProjectsGate } from "@/components/ProjectsGate";

export const metadata: Metadata = {
  title: "Brand Visibility",
  description:
    "Check how often your brand appears across commercial projects nationwide, and find the projects where your category is still open.",
};

// No server-side data fetch here anymore -- this used to call
// getSampleProjects(2000) at build time and pass the full raw sample as a
// prop to VisibilityPanel, which serialized all 2,000 real project records
// into this page's public static HTML (readable by anyone, signed in or
// not). VisibilityPanel now fetches its own sample client-side, behind
// ProjectsGate, against the now-auth-required /v1/projects endpoint --
// same pattern components/ProjectsDashboard.tsx already used.
export default function VisibilityPage() {
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
        <ProjectsGate>
          <VisibilityPanel />
        </ProjectsGate>
      </div>
    </div>
  );
}
