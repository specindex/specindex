import Link from "next/link";
import { getStats, getSampleProjects } from "@/lib/projects";
import { formatUsd, typeLabel } from "@/lib/format";
import { getTopCounties, getVisibilitySnapshot } from "@/lib/stats";
import { StatusPill } from "@/components/StatusPill";

const DEMO_BRAND = "Acuity Brands";
const DEMO_CATEGORY = "lighting";

export async function ProductMock() {
  // Was getProjects()+getCorpus() -- the full ~175K+-row corpus, ~3,500
  // sequential requests -- for a marketing mockup that only ever shows 4
  // preview cards and a handful of counties. This is what was actually
  // timing out the homepage build the whole time (confirmed live
  // 2026-07-29): every fix applied directly to app/page.tsx made zero
  // difference because the real full-corpus crawl was happening here, in a
  // child component, not there.
  const stats = await getStats();
  const projects = await getSampleProjects(500);
  const preview = projects.slice(0, 4);
  const counties = getTopCounties(projects, 6);
  const { categoryHits, stillOpen } = getVisibilitySnapshot(
    projects,
    DEMO_BRAND,
    DEMO_CATEGORY,
  );
  const stateLabel = stats.states > 1 ? `${stats.states} states` : "national index";

  return (
    <div className="card-elevated overflow-hidden">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-gray-100)] px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded bg-[var(--color-green)] text-[10px] font-bold text-white">
            S
          </span>
          <span className="text-xs font-medium text-[var(--color-gray-600)]">
            SpecIndex · {stateLabel}
          </span>
        </div>
        <span className="font-mono text-[10px] text-[var(--color-gray-400)]">
          Live · 1000+ projects
        </span>
      </div>

      <div className="grid gap-0 md:grid-cols-[1fr_1.1fr]">
        <div className="border-b border-[var(--color-border)] p-4 md:border-b-0 md:border-r">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
            Top counties
          </p>
          <div className="mt-3 grid grid-cols-3 gap-1">
            {counties.map((c, i) => (
              <div
                key={c}
                className={`rounded px-1.5 py-1 text-center font-mono text-[9px] ${
                  i < 3
                    ? "bg-[var(--color-green-light)] font-semibold text-[var(--color-green)]"
                    : "bg-[var(--color-gray-100)] text-[var(--color-gray-600)]"
                }`}
              >
                {c}
              </div>
            ))}
          </div>
          <p className="mt-4 font-mono text-[10px] text-[var(--color-gray-600)]">
            {DEMO_CATEGORY} · still early enough
          </p>
          <p className="font-mono text-2xl font-bold text-[var(--color-green)]">
            {stillOpen.length}
          </p>
          <p className="mt-1 text-[10px] text-[var(--color-gray-400)]">
            of {categoryHits.length} projects needing {DEMO_CATEGORY} are in planning or
            permitting
          </p>
        </div>

        <div className="max-h-[280px] overflow-y-auto p-3">
          {preview.map((p) => (
            <Link
              key={p.id}
              href={`/project/${p.id}/`}
              className="mb-2 block rounded-md border border-[var(--color-border)] p-2.5 transition hover:border-[var(--color-amber)]"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-xs font-semibold leading-snug">{p.name}</p>
                <StatusPill status={p.status} />
              </div>
              <p className="mt-1 text-[10px] text-[var(--color-gray-600)]">
                {p.city} · {typeLabel(p.project_type)}
              </p>
              <p className="mt-1 font-mono text-[10px] font-medium text-[var(--color-green)]">
                {formatUsd(p.estimated_value_usd)}
              </p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
