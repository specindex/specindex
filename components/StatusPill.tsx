// Colors track how open the spec window still is, not an arbitrary hue per
// status -- planning/permitting/design are all "still early enough to
// influence," bidding is narrowing, under_construction is mostly locked
// in. A rep scanning a list of cards should read urgency at a glance
// without opening each one (see docs/ROADMAP.md item 47/48).
const tones: Record<string, string> = {
  planning: "bg-[var(--color-green-light)] text-[var(--color-green)] border-green-200",
  permitting: "bg-[var(--color-green-light)] text-[var(--color-green)] border-green-200",
  design: "bg-[var(--color-green-light)] text-[var(--color-green)] border-green-200",
  bidding: "bg-amber-50 text-amber-900 border-amber-200",
  under_construction: "bg-red-50 text-red-800 border-red-200",
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
