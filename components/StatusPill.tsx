const tones: Record<string, string> = {
  planning: "bg-amber-50 text-amber-900 border-amber-200",
  design: "bg-sky-50 text-sky-900 border-sky-200",
  permitting: "bg-violet-50 text-violet-900 border-violet-200",
  bidding: "bg-orange-50 text-orange-900 border-orange-200",
  under_construction: "bg-[var(--color-green-light)] text-[var(--color-green)] border-green-200",
};

export function StatusPill({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
        tones[status] ?? "bg-[var(--color-gray-100)] text-[var(--color-gray-600)] border-[var(--color-border)]"
      }`}
    >
      {status.replaceAll("_", " ")}
    </span>
  );
}
