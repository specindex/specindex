import type { MetadataRoute } from "next";
import { getProjectIds } from "@/lib/projects";

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

  const projectIds = await getProjectIds();

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
