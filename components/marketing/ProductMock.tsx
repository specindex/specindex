import Link from "next/link";
import { getProjects } from "@/lib/projects";
import { formatUsd, typeLabel } from "@/lib/format";
import { StatusPill } from "@/components/StatusPill";

export function ProductMock() {
  const projects = getProjects().slice(0, 4);

  return (
    <div className="card-elevated overflow-hidden">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-gray-100)] px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded bg-[var(--color-green)] text-[10px] font-bold text-white">
            S
          </span>
          <span className="text-xs font-medium text-[var(--color-gray-600)]">
            SpecIndex · Georgia
          </span>
        </div>
        <span className="font-mono text-[10px] text-[var(--color-gray-400)]">
          Live
        </span>
      </div>

      <div className="grid gap-0 md:grid-cols-[1fr_1.1fr]">
        <div className="border-b border-[var(--color-border)] p-4 md:border-b-0 md:border-r">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
            Open projects · Fulton
          </p>
          <div className="mt-3 grid grid-cols-3 gap-1">
            {["Fulton", "Chatham", "Gwinnett", "Bibb", "Henry", "Effingham"].map(
              (c, i) => (
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
              ),
            )}
          </div>
          <p className="mt-4 font-mono text-[10px] text-[var(--color-gray-600)]">
            Brand mention rate
          </p>
          <p className="font-mono text-2xl font-bold text-[var(--color-green)]">12%</p>
          <p className="mt-1 text-[10px] text-[var(--color-gray-400)]">
            vs 34% category opportunity
          </p>
        </div>

        <div className="max-h-[280px] overflow-y-auto p-3">
          {projects.map((p) => (
            <Link
              key={p.id}
              href={`/projects/${p.id}/`}
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
