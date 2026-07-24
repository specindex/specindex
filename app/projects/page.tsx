import type { Metadata } from "next";
import { ProjectSearch } from "@/components/ProjectSearch";
import { getCorpus, getProjects } from "@/lib/projects";

export const metadata: Metadata = {
  title: "Georgia Projects",
  description:
    "Search open commercial construction projects across Georgia — status, specs, teams, and manufacturer watch lists.",
};

export default function ProjectsPage() {
  const projects = getProjects();
  const corpus = getCorpus();

  return (
    <div className="bg-[var(--color-bg)]">
      <div className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl px-5 py-12 md:px-8 md:py-16">
          <p className="text-eyebrow">{corpus.geography}</p>
          <h1 className="mt-3 text-hero">Open commercial projects</h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--color-gray-600)]">
            {projects.length} projects indexed · captured {corpus.generated_at}
          </p>
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <ProjectSearch projects={projects} />
        {corpus.notes && (
          <p className="mt-10 max-w-3xl text-xs leading-relaxed text-[var(--color-gray-400)]">
            Notes: {corpus.notes}
          </p>
        )}
      </div>
    </div>
  );
}
