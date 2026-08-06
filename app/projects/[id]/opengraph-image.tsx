import { ImageResponse } from "next/og";
import { getFeaturedProjectIds, getProject } from "@/lib/projects";
import { formatUsd, stateName, typeLabel } from "@/lib/format";
import { scopeStaticParams } from "@/lib/buildScope";

// ROADMAP.md item 49 (P1): per-project OG images. Rendered at `next build`
// time -- this is a static export (see next.config.ts), so this file only
// runs for the same statically-generated project ids page.tsx uses
// (generateStaticParams below matches getFeaturedProjectIds there); every
// other project falls back to Next's default OG behavior via
// app/projects/view/page.tsx, the client-rendered path for the long tail.
export const alt = "SpecIndex project";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export async function generateStaticParams() {
  const ids = await getFeaturedProjectIds();
  // OG images are rendered images, the most expensive page type per unit.
  return scopeStaticParams(ids.map((id) => ({ id })), "projects/[id]/opengraph-image");
}

export default async function OpengraphImage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const project = await getProject(id);

  const name = project?.name ?? "SpecIndex";
  const state = stateName(project?.state);
  const city = project?.city ?? "";
  const type = project?.project_type ? typeLabel(project.project_type) : "";
  const value = formatUsd(project?.estimated_value_usd ?? null);
  const score = project?.score?.total;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px",
          backgroundColor: "#0f1210",
          color: "#f6f4ef",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 40,
              height: 40,
              borderRadius: 8,
              backgroundColor: "#2f6b3a",
              color: "white",
              fontSize: 20,
              fontWeight: 700,
            }}
          >
            S
          </div>
          <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: 1 }}>SPECINDEX</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 20, color: "#9a9c94", textTransform: "uppercase", letterSpacing: 2 }}>
            {[city, state].filter(Boolean).join(", ") + (type ? ` · ${type}` : "")}
          </div>
          <div style={{ fontSize: 52, fontWeight: 700, lineHeight: 1.15, maxWidth: 1000 }}>
            {name}
          </div>
        </div>

        <div style={{ display: "flex", gap: 40 }}>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ fontSize: 16, color: "#9a9c94", textTransform: "uppercase", letterSpacing: 1 }}>
              Estimated value
            </div>
            <div style={{ fontSize: 32, fontWeight: 700, color: "#6fbf7b" }}>{value}</div>
          </div>
          {typeof score === "number" && (
            <div style={{ display: "flex", flexDirection: "column" }}>
              <div style={{ fontSize: 16, color: "#9a9c94", textTransform: "uppercase", letterSpacing: 1 }}>
                Priority score
              </div>
              <div style={{ fontSize: 32, fontWeight: 700, color: "#6fbf7b" }}>{score}/100</div>
            </div>
          )}
        </div>
      </div>
    ),
    { ...size },
  );
}
