import type { Metadata } from "next";
import { VisibilityPanel } from "@/components/VisibilityPanel";
import { getProjects } from "@/lib/projects";

export const metadata: Metadata = {
  title: "Brand Visibility",
  description:
    "See if your brand is mentioned across Georgia open projects and compare category opportunities.",
};

export default function VisibilityPage() {
  const projects = getProjects();

  return (
    <div className="bg-[var(--color-bg)]">
      <div className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl px-5 py-12 md:px-8 md:py-16">
          <p className="text-eyebrow">Brand intelligence</p>
          <h1 className="mt-3 text-hero">Visibility compare</h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--color-gray-600)]">
            Check mention coverage for your brand against SpecIndex&apos;s Georgia
            corpus, then jump to opportunity projects.
          </p>
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <VisibilityPanel projects={projects} />
      </div>
    </div>
  );
}
