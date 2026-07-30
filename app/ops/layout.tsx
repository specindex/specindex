import Link from "next/link";

// Admin portal shell (docs/architecture-2026/02-identity-portals.md Phase
// 4): one navigation surface consolidating links to every internal page,
// rather than each staying an unlinked URL only findable by knowing it
// exists. Deliberately does NOT change any page's own auth requirement --
// /ops, /coverage, /map stay unauthenticated-but-noindex (they expose only
// operational metadata, per that doc's own reasoning); /ops/crm and
// /ops/customer stay real-auth-gated (they render PII). This layout is
// just a shared nav bar, not a new security boundary.
const ADMIN_LINKS = [
  { href: "/ops/", label: "Ops" },
  { href: "/ops/crm/", label: "CRM" },
  { href: "/coverage/", label: "Coverage" },
  { href: "/map/", label: "Map" },
];

export default function OpsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-[var(--color-bg)]">
      <nav className="border-b border-[var(--color-border)] bg-[var(--color-ink)]">
        <div className="mx-auto flex max-w-6xl items-center gap-1 px-5 py-2.5 md:px-8">
          <span className="mr-3 text-xs font-semibold uppercase tracking-wider text-white/50">
            Internal
          </span>
          {ADMIN_LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="rounded-md px-3 py-1.5 text-sm font-medium text-white/80 hover:bg-white/10 hover:text-white"
            >
              {l.label}
            </Link>
          ))}
        </div>
      </nav>
      {children}
    </div>
  );
}
