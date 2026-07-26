import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { StatusPill } from "@/components/StatusPill";
import { ProjectScoreBadge } from "@/components/ProjectScoreBadge";
import { ProjectTimeline } from "@/components/ProjectTimeline";
import { ProjectNews } from "@/components/ProjectNews";
import { ProjectLocationMap } from "@/components/ProjectLocationMap";
import { formatDate, formatSf, formatUsd, stateName, typeLabel } from "@/lib/format";
import { getProject, getProjectIds } from "@/lib/projects";

type Props = { params: Promise<{ id: string }> };

export async function generateStaticParams() {
  const ids = await getProjectIds();
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
    <article className="bg-[var(--color-bg)]">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(projectJsonLd(project)) }}
      />

      {/* Sticky title+score bar -- stays visible while scrolling the long
          write-up below, so the score and identity don't disappear the
          moment someone starts reading (per docs/ROADMAP.md item 52). */}
      <div className="sticky top-14 z-40 border-b border-[var(--color-border)] bg-white/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-5 py-2.5 md:px-8">
          <p className="truncate text-sm font-medium text-[var(--color-ink)]">{project.name}</p>
          {project.score && (
            <span className="shrink-0 rounded-full bg-[var(--color-amber)]/10 px-2.5 py-1 text-xs font-semibold text-[var(--color-amber)]">
              🔥 {project.score.total}/100
            </span>
          )}
        </div>
      </div>

      <div className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-14">
          <Link
            href="/projects/"
            className="text-sm font-medium text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
          >
            ← All projects
          </Link>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <StatusPill status={project.status} />
            <span className="text-sm text-[var(--color-gray-600)]">
              {typeLabel(project.project_type)}
            </span>
          </div>
          <h1 className="mt-3 text-hero">{project.name}</h1>
          <p className="mt-2 font-mono text-sm text-[var(--color-gray-400)]">
            {project.spx_id}
          </p>
          <p className="mt-2 text-lg text-[var(--color-gray-600)]">
            {project.city}
            {project.county ? `, ${project.county} County` : ""},{" "}
            {stateName(project.state)}
          </p>
        </div>
      </div>

      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 md:px-8 md:py-12 lg:grid-cols-3">
        {/* Main column */}
        <div className="lg:col-span-2">
          <dl className="card grid gap-4 p-6 sm:grid-cols-2">
            <Fact label="Project ID" value={project.spx_id} mono />
            <Fact label="Estimated value" value={formatUsd(project.estimated_value_usd)} />
            <Fact label="Square footage" value={formatSf(project.square_footage)} />
            <Fact
              label="Opened / announced"
              value={formatDate(project.opened_or_announced_date)}
            />
            <Fact label="Owner" value={project.owner || "Not reported"} />
            <Fact
              label="General contractor"
              value={project.general_contractor || "Not reported"}
            />
            <Fact label="Architect" value={project.architect || "Not reported"} />
            <Fact
              label="Brands mentioned"
              value={
                project.mentioned_brands.length
                  ? project.mentioned_brands.join(", ")
                  : "None in public seed"
              }
            />
          </dl>

          <section className="mt-8">
            <h2 className="text-xl font-semibold">Project overview</h2>
            <p className="mt-3 text-base leading-relaxed text-[var(--color-gray-600)]">
              {project.description}
            </p>
          </section>

          <section className="mt-8">
            <h2 className="text-xl font-semibold">Key specs</h2>
            <ul className="mt-4 list-disc space-y-2 pl-5 text-[var(--color-gray-600)]">
              {project.key_specs.map((spec) => (
                <li key={spec}>{spec}</li>
              ))}
            </ul>
          </section>

          <section className="mt-8 rounded-lg bg-[var(--color-green)] p-6 text-white">
            <h2 className="text-lg font-semibold text-[var(--color-amber)]">
              Still open for manufacturers
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-white/90">
              {project.open_for}
            </p>
          </section>

          <section className="mt-8">
            <h2 className="text-xl font-semibold">Manufacturer watch list</h2>
            <ul className="mt-4 flex flex-wrap gap-2">
              {project.competitor_watch.map((item) => (
                <li
                  key={item}
                  className="rounded-full border border-[var(--color-border)] bg-white px-3 py-1.5 text-sm text-[var(--color-gray-600)]"
                >
                  {item}
                </li>
              ))}
            </ul>
          </section>

          <div className="mt-6">
            <ProjectTimeline events={project.timeline} />
          </div>

          <div className="mt-12 flex flex-wrap gap-3">
            <Link
              href={`/visibility/${
                project.competitor_watch[0]
                  ? `?category=${encodeURIComponent(project.competitor_watch[0])}`
                  : ""
              }`}
              className="btn btn-primary"
            >
              Run a brand check for this project
            </Link>
            <Link href="/projects/" className="btn btn-outline">
              Back to all projects
            </Link>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <ProjectScoreBadge score={project.score} />
          <ProjectLocationMap
            latitude={project.latitude}
            longitude={project.longitude}
            name={project.name}
            city={project.city}
            county={project.county}
            state={project.state}
          />
          <ProjectNews news={project.news} />
        </div>
      </div>
    </article>
  );
}

function Fact({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
        {label}
      </dt>
      <dd className={`mt-1 text-sm font-medium ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}
