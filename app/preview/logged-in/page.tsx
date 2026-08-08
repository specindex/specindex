import { getProject } from "@/lib/projects";
import { WorkspacePreview } from "@/components/preview/WorkspacePreview";

// PREVIEW ONLY -- not linked from anywhere, not in the sitemap, noindex.
//
// Renders the logged-in workspace redesign (docs/logged-in-redesign/) against
// the REAL Maine record so the design can be judged on real data rather than
// on the mock's placeholders. Built as its own route so nothing here can
// affect /project/[id]/, which is live.
//
// Why Maine: it is the handoff's own demo record, and it is the useful case
// precisely because the mock got it wrong. The mock was traced from the PUBLIC
// page, which serves a gated teaser, so it shows "0 manufacturers cited /
// 0 documents held / 0 divisions in scope". Signed in, this same project has
// 17 citations, 6 documents and 15 divisions. Judging the design against the
// mock's zeros would tune it for a state this record is never in.
const DEMO_ID = "me-portal-maine-vertical-3820";

export const metadata = {
  title: "Workspace preview",
  robots: { index: false, follow: false },
};

export default async function LoggedInPreviewPage() {
  const project = await getProject(DEMO_ID);
  return <WorkspacePreview project={project ?? null} />;
}
