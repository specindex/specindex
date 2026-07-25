import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { StatusPill } from "@/components/StatusPill";
import { formatDate, formatSf, formatUsd, stateName, typeLabel } from "@/lib/format";
import { getProjectById, getProjectIds } from "@/lib/projects";

type Props = { params: Promise<{ id: string }> };

export async function generateStaticParams() {
  const ids = await getProjectIds();
  return ids.map((id) => ({ id }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const project = await getProjectById(id);
  if (!project) return { title: "Project" };
  return {
    title: project.name,
    description: project.description.slice(0, 160),
  };
}

export default async function ProjectDetailPage({ params }: Props) {
  const { id } = await params;
  const project = await getProjectById(id);
  if (!project) notFound();

  return (
    <article className="bg-[var(--color-bg)]">
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
            Project ID: {project.id}
          </p>
          <p className="mt-2 text-lg text-[var(--color-gray-600)]">
            {project.city}
            {project.county ? `, ${project.county} County` : ""},{" "}
            {stateName(project.state)}
          </p>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <dl className="card grid gap-4 p-6 sm:grid-cols-2 lg:grid-cols-3">
          <Fact label="Project ID" value={project.id} mono />
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

        <section className="mt-10 max-w-3xl">
          <h2 className="text-xl font-semibold">Project overview</h2>
          <p className="mt-3 text-base leading-relaxed text-[var(--color-gray-600)]">
            {project.description}
          </p>
        </section>

        <section className="mt-10 max-w-3xl">
          <h2 className="text-xl font-semibold">Key specs</h2>
          <ul className="mt-4 list-disc space-y-2 pl-5 text-[var(--color-gray-600)]">
            {project.key_specs.map((spec) => (
              <li key={spec}>{spec}</li>
            ))}
          </ul>
        </section>

        <section className="mt-10 max-w-3xl rounded-lg bg-[var(--color-green)] p-6 text-white">
          <h2 className="text-lg font-semibold text-[var(--color-amber)]">
            Still open for manufacturers
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/90">
            {project.open_for}
          </p>
        </section>

        <section className="mt-10 max-w-3xl">
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

        {project.sources.length > 0 && (
          <section className="mt-10 max-w-3xl">
            <h2 className="text-xl font-semibold">Sources</h2>
            <ul className="mt-3 space-y-2 text-sm text-[var(--color-gray-600)]">
              {project.sources.map((s) => (
                <li key={`${s.title}-${s.url}`}>
                  {s.url ? (
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[var(--color-green)] underline underline-offset-2"
                    >
                      {s.title || s.url}
                    </a>
                  ) : (
                    <span>{s.title}</span>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        <div className="mt-12 flex flex-wrap gap-3">
          <Link href="/visibility/" className="btn btn-primary">
            Compare brand visibility
          </Link>
          <Link href="/projects/" className="btn btn-outline">
            Back to all projects
          </Link>
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
