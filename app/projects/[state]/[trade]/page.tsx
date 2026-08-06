import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getStateSample, getStates } from "@/lib/projects";
import { DIVISIONS, divisionBySlug, getProjectsForDivision } from "@/lib/divisions";
import { stateName, formatUsd } from "@/lib/format";
import { isStillOpen } from "@/lib/stats";
import { StatusPill } from "@/components/StatusPill";
import { scopeStaticParams } from "@/lib/buildScope";

type Props = { params: Promise<{ state: string; trade: string }> };

// ROADMAP.md item 49 (P1): programmatic SEO hub pages, one per real
// (state, division) combination that actually has coverage. Built the
// same way every other route here is -- generateStaticParams() at `next
// build` time, no ISR needed (the doc that proposed this assumed a
// server runtime this static-export site doesn't have). Empty combos are
// skipped rather than emitted as thin/empty pages, which would be a real
// SEO liability, not just wasted build time.
export async function generateStaticParams() {
  // Truncate the STATE LIST, not the resulting params. getStateSample() is a
  // network round-trip per state, so trimming the output afterwards would
  // still pay the full fetch cost for all 50 -- the expensive part is the
  // loop, not the array it produces.
  const states = scopeStaticParams(await getStates(), "projects/[state]/[trade]");
  const params: { state: string; trade: string }[] = [];
  for (const state of states) {
    const sample = await getStateSample(state);
    if (sample.length === 0) continue;
    for (const division of DIVISIONS) {
      if (getProjectsForDivision(sample, division).length > 0) {
        params.push({ state: state.toLowerCase(), trade: division.slug });
      }
    }
  }
  return params;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { state, trade } = await params;
  const division = divisionBySlug(trade);
  if (!division) return { title: "Projects" };
  const name = stateName(state);
  return {
    title: `${division.name} projects in ${name}`,
    description: `Open commercial construction projects in ${name} needing ${division.plain.toLowerCase()}, ranked by priority score.`,
    alternates: { canonical: `/projects/${state.toLowerCase()}/${division.slug}/` },
  };
}

export default async function StateTradeHubPage({ params }: Props) {
  const { state, trade } = await params;
  const division = divisionBySlug(trade);
  if (!division) notFound();

  const sample = await getStateSample(state);
  const matches = getProjectsForDivision(sample, division);
  if (matches.length === 0) notFound();

  const name = stateName(state);
  const stillOpen = matches.filter(isStillOpen);
  const top = matches.slice(0, 20);

  return (
    <div className="bg-[var(--color-bg)]">
      <div className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl px-5 py-12 md:px-8 md:py-16">
          <p className="text-eyebrow">
            {name} · Division {division.code}
          </p>
          <h1 className="mt-3 text-hero">
            {division.name} projects in {name}
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--color-gray-600)]">
            {division.plain}. Usually specified by the {division.specifiedBy.toLowerCase()}.
            Counted across our {sample.length} highest-priority scored {name} projects,{" "}
            <strong className="text-[var(--color-ink)]">{matches.length}</strong> need this
            division and <strong className="text-[var(--color-ink)]">{stillOpen.length}</strong>{" "}
            are still in planning or permitting.
          </p>
          <Link
            href="/projects/"
            className="mt-6 inline-block text-sm font-semibold text-[var(--color-green)] hover:underline"
          >
            Search the full index →
          </Link>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <ul className="divide-y divide-[var(--color-border)] rounded-lg border border-[var(--color-border)] bg-white">
          {top.map((p) => (
            <li key={p.id}>
              <Link
                href={`/projects/${p.id}/`}
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-4 hover:bg-[var(--color-gray-100)]"
              >
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{p.name}</span>
                    <StatusPill status={p.status} />
                  </div>
                  <p className="text-sm text-[var(--color-gray-600)]">
                    {p.city} · {formatUsd(p.estimated_value_usd)}
                  </p>
                </div>
                <span className="text-sm font-medium text-[var(--color-green)]">
                  View specs →
                </span>
              </Link>
            </li>
          ))}
        </ul>

        <div className="mt-10">
          <h2 className="text-lg font-semibold">Other divisions in {name}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {DIVISIONS.filter(
              (d) => d.code !== division.code && getProjectsForDivision(sample, d).length > 0,
            ).map((d) => (
              <Link
                key={d.code}
                href={`/projects/${state.toLowerCase()}/${d.slug}/`}
                className="rounded-full border border-[var(--color-border)] bg-white px-3 py-1.5 text-xs font-medium text-[var(--color-gray-600)] hover:border-[var(--color-green)] hover:text-[var(--color-ink)]"
              >
                {d.name}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
