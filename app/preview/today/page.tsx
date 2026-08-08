import { getStateSample } from "@/lib/projects";
import { TodayPreview } from "@/components/preview/TodayPreview";

// Screen 1 of the logged-in workspace redesign, rendered against the real
// Maine territory. noindex and unlinked: this is a work-in-progress workspace
// shipped to production so it can be reviewed on the live site, and it must not
// enter the sitemap or compete with /project/* for indexing.
//
// No seed data. lib/previewSeed.ts is deleted; see TodayPreview for why.
export const metadata = {
  title: "Today",
  robots: { index: false, follow: false },
};

export default async function TodayPreviewPage() {
  const all = await getStateSample("ME", 300);
  // "with documents held" is a claim about our coverage, so it counts what we
  // actually hold rather than has_documents, which can be set from a portal
  // listing that advertised an attachment we never retrieved.
  const documented = all.filter((p) => (p.document_count ?? 0) > 0).length;
  return <TodayPreview projects={all} total={all.length} documented={documented} />;
}
