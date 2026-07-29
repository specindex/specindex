import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ProjectDetailView } from "@/components/ProjectDetailView";
import { getProject, getFeaturedProjectIds } from "@/lib/projects";

type Props = { params: Promise<{ id: string }> };

// Only the highest-scored projects are statically pre-rendered here (real
// SEO/JSON-LD, built once at deploy time). Every other project -- the vast
// majority as the corpus scales toward 6.5M+ rows -- is served by
// app/projects/view/page.tsx, a client-rendered fallback that Firebase
// Hosting routes to for any /projects/{id}/ path without a matching static
// file (see firebase.json's rewrite + docs/ROADMAP.md item 44's follow-up).
export async function generateStaticParams() {
  const ids = await getFeaturedProjectIds();
  return ids.map((id) => ({ id }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const project = await getProject(id);
  if (!project) return { title: "Project" };
  return {
    title: project.name,
    description: project.description.slice(0, 160),
    // Absolute per-project URL so tracking params (?ref=, ?utm=) on shared
    // links don't get indexed as separate pages competing with this one.
    alternates: { canonical: `/projects/${project.id}/` },
  };
}

// Built only from our own verified DB fields (name/address/description/
// value) -- never from outside "facts" an LLM might supply, since those
// have been demonstrated to disagree with our sourced data (see
// docs/ROADMAP.md item 50). GeoCoordinates is omitted entirely when we
// don't have real coordinates, rather than guessing a city centroid.
function projectJsonLd(project: NonNullable<Awaited<ReturnType<typeof getProject>>>) {
  const address: Record<string, string> = {
    "@type": "PostalAddress",
    addressLocality: project.city || project.county || "",
    addressRegion: project.state ?? "",
    addressCountry: "US",
  };
  const jsonLd: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "Project",
    name: project.name,
    description: project.description,
    address,
  };
  if (project.latitude != null && project.longitude != null) {
    jsonLd.geo = {
      "@type": "GeoCoordinates",
      latitude: project.latitude,
      longitude: project.longitude,
    };
  }
  return jsonLd;
}

export default async function ProjectDetailPage({ params }: Props) {
  const { id } = await params;
  const project = await getProject(id);
  if (!project) notFound();

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(projectJsonLd(project)) }}
      />
      <ProjectDetailView project={project} />
    </>
  );
}
