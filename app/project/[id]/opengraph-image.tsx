import { readFile } from "node:fs/promises";
import path from "node:path";
import { ImageResponse } from "next/og";
import { getFeaturedProjectIds, getProject } from "@/lib/projects";
import { formatUsd, stateName, typeLabel } from "@/lib/format";
import { scopeStaticParams } from "@/lib/buildScope";

// THE OG CARD IS THE ONE SURFACE THAT RENDERS IN SOMEONE ELSE'S FEED.
// It was drawn with fontFamily "sans-serif", i.e. whatever the renderer
// happened to default to, while every route on the site uses Geist. That is
// backwards: a LinkedIn or Slack preview is where brand consistency is most
// visible and least controllable, and it was the only place in the app still
// off-brand after the 2026-08-08 migration.
//
// Satori (what next/og uses) cannot read CSS variables -- the page's
// --font-geist-sans means nothing here -- so the bytes have to be handed over
// directly. Three constraints, each learned by hitting it:
//   - TTF, not WOFF2. Satori fails the build outright with "Unsupported
//     OpenType signature wOF2". The geist package ships both; take the .ttf.
//   - Static cuts, not Geist-Variable. Satori does not interpolate variable
//     axes, so a variable file renders every weight identically.
//   - Only the three weights this card uses (400/600/700). Loading all nine
//     would embed ~1MB per image for no visible gain.
//
// Read from node_modules at BUILD time. This file only ever runs during
// `next build` (static export, see next.config.ts), so there is no request
// path where a missing file could 500 a live page -- it would fail the build
// loudly instead, which is the right place for it to fail.
const GEIST_DIR = path.join(process.cwd(), "node_modules/geist/dist/fonts/geist-sans");

async function geistFonts() {
  const [regular, semibold, bold] = await Promise.all([
    readFile(path.join(GEIST_DIR, "Geist-Regular.ttf")),
    readFile(path.join(GEIST_DIR, "Geist-SemiBold.ttf")),
    readFile(path.join(GEIST_DIR, "Geist-Bold.ttf")),
  ]);
  return [
    { name: "Geist", data: regular, weight: 400 as const, style: "normal" as const },
    { name: "Geist", data: semibold, weight: 600 as const, style: "normal" as const },
    { name: "Geist", data: bold, weight: 700 as const, style: "normal" as const },
  ];
}

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
  return scopeStaticParams(ids.map((id) => ({ id })), "project/[id]/opengraph-image");
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
          fontFamily: "Geist",
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
    { ...size, fonts: await geistFonts() },
  );
}
