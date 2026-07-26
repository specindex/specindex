import type { ProjectTimelineEvent } from "@/lib/types";
import { formatDate } from "@/lib/format";

type Props = {
  events: ProjectTimelineEvent[];
};

const EVENT_LABELS: Record<string, string> = {
  Announced: "Announced",
  Design_Started: "Design started",
  Permit_Issued: "Permit issued",
  Bid_Opened: "Bid opened",
  Awarded: "Awarded",
  Groundbroken: "Groundbroken",
};

export function ProjectTimeline({ events }: Props) {
  if (events.length === 0) return null;

  return (
    <div className="card p-4 md:p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-gray-400)]">
        Timeline
      </h2>
      <ol className="mt-4 space-y-4">
        {events.map((e, i) => (
          <li key={`${e.event_type}-${e.event_date}-${i}`} className="flex gap-3">
            <div className="flex flex-col items-center">
              <span className="h-2.5 w-2.5 rounded-full bg-[var(--color-green)]" />
              {i < events.length - 1 && (
                <span className="mt-1 w-px flex-1 bg-[var(--color-border)]" />
              )}
            </div>
            <div className="pb-1">
              <p className="text-sm font-medium">{EVENT_LABELS[e.event_type] ?? e.event_type}</p>
              <p className="text-xs text-[var(--color-gray-600)]">
                {formatDate(e.event_date ?? undefined)} · {e.source_name}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
