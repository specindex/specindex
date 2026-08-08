"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ProjectDetailUpgrade } from "@/components/project-detail/ProjectDetailUpgrade";
import { ProjectsGate } from "@/components/ProjectsGate";
import { getProject } from "@/lib/projects";
import type { Project } from "@/lib/types";

// Fallback renderer for any /project/{id}/ path that ISN'T one of the
// statically pre-generated pages -- Firebase Hosting rewrites unmatched
// /project/*/ requests here (see firebase.json) while keeping the
// original URL in the address bar, so the real id is read from
// window.location.pathname rather than a route param. This is what makes
// project detail pages scale to any corpus size: this one file is built
// once, and serves every project that isn't in the curated top-N static
// set (see getFeaturedProjectIds in lib/projects.ts).
//
// Known tradeoff, not yet solved: this page's *raw* HTML (before JS runs)
// has no project-specific <title>/description/JSON-LD -- real SEO for the
// long tail needs actual SSR, which means moving off static export
// (docs/ROADMAP.md item 42's deferred plan). This client-render fix
// unblocks the crash and unlimited scale today; it does not fully replace
// that migration for search-crawler-quality metadata on the long tail.
export default function ProjectViewShell() {
  return (
    <ProjectsGate>
      <ProjectViewContent />
    </ProjectsGate>
  );
}

// Split from the default export so the getProject() fetch below only fires
// once ProjectsGate has confirmed a signed-in session -- it lives inside the
// gated child, not a parent that mounts unconditionally, so an anonymous
// visitor never triggers the request that would return real project data.
function ProjectViewContent() {
  const [project, setProject] = useState<Project | null | undefined>(undefined);

  useEffect(() => {
    const segments = window.location.pathname.split("/").filter(Boolean);
    // Expect /project/{id}/ -- if this file is hit some other way (direct
    // visit to /project/view/), there's no id to resolve.
    const id = segments[0] === "project" && segments[1] !== "view" ? segments[1] : null;
    if (!id) {
      setProject(null);
      return;
    }
    let cancelled = false;
    getProject(id).then((p) => {
      if (!cancelled) setProject(p ?? null);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (project) document.title = `${project.name} | SpecIndex`;
  }, [project]);

  if (project === undefined) {
    return (
      <div className="mx-auto max-w-3xl px-5 py-24 text-center md:px-8">
        <p className="text-[var(--color-gray-600)]">Loading project…</p>
      </div>
    );
  }

  if (project === null) {
    return (
      <div className="mx-auto max-w-3xl px-5 py-24 text-center md:px-8">
        <h1 className="text-hero">Project not found</h1>
        <p className="mt-3 text-[var(--color-gray-600)]">
          That project ID doesn&apos;t match anything in the index.
        </p>
        <Link href="/projects/" className="btn btn-primary mt-8 inline-flex">
          Back to all projects
        </Link>
      </div>
    );
  }

  return <ProjectDetailUpgrade initialProject={project} />;
}
