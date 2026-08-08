import { getStateSample } from "@/lib/projects";
import { DiscoverPreview } from "@/components/preview/DiscoverPreview";

// PREVIEW ONLY -- unlinked, noindex, separate route so it cannot affect
// anything live. Screen 2 of docs/logged-in-redesign/, rendered against the
// real Maine territory rather than the mock's illustrative rows.
export const metadata = {
  title: "Discover preview",
  robots: { index: false, follow: false },
};

export default async function DiscoverPreviewPage() {
  const all = await getStateSample("ME", 300);
  // Priority score desc, nulls last. The handoff's default sort, and the only
  // one that puts the record a rep should open first at the top.
  const sorted = [...all].sort((a, b) => (b.score?.total ?? -1) - (a.score?.total ?? -1));
  return <DiscoverPreview projects={sorted} total={all.length} />;
}
