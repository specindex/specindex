import type { ProjectScore } from "@/lib/types";

type Props = {
  score: ProjectScore;
};

export function ProjectScoreBadge({ score }: Props) {
  if (!score) {
    return (
      <div className="card p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
          Priority score
        </p>
        <p className="mt-1 text-sm text-[var(--color-gray-600)]">Not yet computed</p>
      </div>
    );
  }

  const tier =
    score.total >= 70
      ? { label: "High priority", cls: "bg-[var(--color-green)]/10 text-[var(--color-green)]" }
      : score.total >= 40
        ? { label: "Watch", cls: "bg-[var(--color-amber)]/10 text-[var(--color-amber)]" }
        : { label: "Low signal", cls: "bg-[var(--color-gray-100)] text-[var(--color-gray-600)]" };

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
          Priority score
        </p>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${tier.cls}`}>
          {tier.label}
        </span>
      </div>
      <p className="mt-1 text-3xl font-semibold tracking-tight">{score.total}
        <span className="text-base font-normal text-[var(--color-gray-400)]">/100</span>
      </p>
      <dl className="mt-3 space-y-1 text-xs text-[var(--color-gray-600)]">
        <div className="flex justify-between">
          <dt>Value</dt>
          <dd className="tabular-nums">{score.value}/40</dd>
        </div>
        <div className="flex justify-between">
          <dt>Recency</dt>
          <dd className="tabular-nums">{score.recency}/35</dd>
        </div>
        <div className="flex justify-between">
          <dt>News coverage</dt>
          <dd className="tabular-nums">{score.news}/25</dd>
        </div>
      </dl>
    </div>
  );
}
