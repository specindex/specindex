import type { MetadataRoute } from "next";
import { getFeaturedProjectIds } from "@/lib/projects";

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
  const projectIds = await getFeaturedProjectIds(2000);

  return [
    ...staticRoutes.map((path) => ({
      url: `${base}/${path}${path ? "/" : ""}`,
      lastModified: new Date("2026-07-24"),
      changeFrequency: "weekly" as const,
      priority: path === "" ? 1 : 0.8,
    })),
    ...projectIds.map((id) => ({
      url: `${base}/projects/${id}/`,
      lastModified: new Date("2026-07-24"),
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),
  ];
}
