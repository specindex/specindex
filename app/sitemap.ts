import type { MetadataRoute } from "next";
import { getFeaturedProjectIds, getStateSample, getStates } from "@/lib/projects";
import { DIVISIONS, getProjectsForDivision } from "@/lib/divisions";
import { isPreviewBuild, PREVIEW_PAGE_LIMIT } from "@/lib/buildScope";

export const dynamic = "force-static";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = "https://specindex.ai";
  const staticRoutes = [
    "",
    "product",
    "how-it-works",
    "pricing",
    "about",
    "projects",
    "visibility",
  ];

  // getProjectIds() paginated the ENTIRE corpus just to list URLs -- timed
  // out the build at ~175K rows (same root cause as /projects/[id]'s crash,
  // see lib/projects.ts). Capped to the same curated top-scored set that
  // actually gets a real statically-rendered page (see
  // getFeaturedProjectIds) -- everything else is client-rendered and a
  // weaker sitemap candidate anyway. Google also caps a single sitemap at
  // 50,000 URLs regardless; a real fix for full coverage is a sitemap
  // index with numbered sub-sitemaps fed by a dedicated lightweight
  // ids-only endpoint, not this file fetching full project rows to throw
  // away everything but `.id`.
  // Preview builds cap this the same way every other route does. The cap
  // landed for pages in #126 but this route was missed, and it alone then
  // exceeded the 300s export limit, failed three retries and BLOCKED all five
  // open PRs at once -- five identical failures from one uncapped file. A
  // sitemap is a list of URLs; ten of them prove the route renders.
  const projectIds = await getFeaturedProjectIds(
    isPreviewBuild() ? PREVIEW_PAGE_LIMIT : 2000,
  );

  // /projects/[state]/[trade]/ pSEO hubs (ROADMAP.md item 49, P1) -- same
  // per-state-sample reuse as that route's own generateStaticParams(), so
  // this doesn't re-fetch every state a second time.
  const allStates = await getStates();
  const states = isPreviewBuild() ? allStates.slice(0, PREVIEW_PAGE_LIMIT) : allStates;

  // Was a serial `await getStateSample(state)` inside a for-loop -- ~50 round
  // trips end to end, which is most of why this route blew the 300s export
  // budget. Fetching them concurrently keeps the output byte-identical on main
  // (same states, same order) while removing the part that actually took the
  // time. The preview cap above is the fail-safe; this is the real fix, and it
  // is what stops the route creeping back over the limit as states are added.
  const samples = await Promise.all(states.map((s) => getStateSample(s)));

  const hubRoutes: { state: string; trade: string }[] = [];
  states.forEach((state, i) => {
    for (const division of DIVISIONS) {
      if (getProjectsForDivision(samples[i], division).length > 0) {
        hubRoutes.push({ state: state.toLowerCase(), trade: division.slug });
      }
    }
  });

  return [
    ...staticRoutes.map((path) => ({
      url: `${base}/${path}${path ? "/" : ""}`,
      lastModified: new Date("2026-07-24"),
      changeFrequency: "weekly" as const,
      priority: path === "" ? 1 : 0.8,
    })),
    ...projectIds.map((id) => ({
      url: `${base}/project/${id}/`,
      lastModified: new Date("2026-07-24"),
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),
    ...hubRoutes.map(({ state, trade }) => ({
      url: `${base}/projects/${state}/${trade}/`,
      lastModified: new Date("2026-07-30"),
      changeFrequency: "weekly" as const,
      priority: 0.5,
    })),
  ];
}
