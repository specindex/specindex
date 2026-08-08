import { getProject } from "@/lib/projects";
import { TodayPreview } from "@/components/preview/TodayPreview";

// PREVIEW ONLY -- unlinked, noindex. Screen 1 of docs/logged-in-redesign/.
//
// Mixes the ONE real Maine record with the handoff's illustrative projects so
// the layout can be judged with both a sparse and a rich row in the same list.
// The banner on the page names which is which; see lib/previewSeed.ts for why
// the seed data is quarantined.
export const metadata = {
  title: "Today preview",
  robots: { index: false, follow: false },
};

export default async function TodayPreviewPage() {
  const realProject = await getProject("me-portal-maine-vertical-3820");
  return <TodayPreview realProject={realProject ?? null} />;
}
