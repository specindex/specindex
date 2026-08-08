"use client";

import { useEffect, useState } from "react";
import { ProjectDetailView } from "@/components/ProjectDetailView";
import { useFirebaseAuthOptional } from "@/components/FirebaseAuthProvider";
import { fetchProjectForSignedInUser } from "@/lib/projects";
import type { Project } from "@/lib/types";

// Separate file from ClientBits.tsx to avoid a circular import:
// ProjectDetailView imports several islands FROM ClientBits, so ClientBits
// can't also import ProjectDetailView back.
//
// The static build only ever bakes in the public teaser (unauthenticated
// build-time fetch, see lib/projects.ts's X-Build-Token path) -- a signed-in
// visitor's session has no effect on that HTML. This wraps the whole
// server-rendered ProjectDetailView tree and, once a signed-in fetch
// returns the full record, swaps `project` wholesale so React re-renders
// everything from the real data (citations, documents, facts, the read
// panel's deep/shallow flip) -- not just a banner. ProjectDetailView itself
// has no "use client" and does no server-only work, so it renders fine
// inside this client boundary; Next bundles it for the browser once it's
// reached from here, same as any other client-tree import.
export function ProjectDetailUpgrade({ initialProject }: { initialProject: Project }) {
  const [project, setProject] = useState(initialProject);
  const { isSignedIn, getToken } = useFirebaseAuthOptional() ?? {
    isLoaded: true,
    isSignedIn: false,
    getToken: async () => null,
  };

  useEffect(() => {
    if (!initialProject.gated || !isSignedIn) return;
    let cancelled = false;
    getToken().then((token) => {
      if (!token || cancelled) return;
      fetchProjectForSignedInUser(initialProject.id, token).then((full) => {
        if (!cancelled && full) setProject(full);
      });
    });
    return () => {
      cancelled = true;
    };
  }, [initialProject, isSignedIn, getToken]);

  return <ProjectDetailView project={project} />;
}
