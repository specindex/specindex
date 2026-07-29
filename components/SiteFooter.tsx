import Link from "next/link";
import { Logo } from "@/components/Logo";

const product = [
  { href: "/product/", label: "Use Cases" },
  { href: "/how-it-works/", label: "How It Works" },
  { href: "/pricing/", label: "Pricing" },
  { href: "/projects/", label: "Projects" },
  { href: "/visibility/", label: "Brand Visibility" },
  { href: "/reporting/", label: "Reporting" },
];

const company = [
  { href: "/about/", label: "About" },
  { href: "mailto:hello@specindex.ai", label: "Contact" },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-[var(--color-border)] bg-white">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-14 md:grid-cols-4 md:px-8">
        <div className="md:col-span-1">
          <div className="flex items-center gap-2">
            <Logo size={28} />
            <span className="text-lg font-semibold">SpecIndex</span>
          </div>
          <p className="mt-3 max-w-xs text-sm leading-relaxed text-[var(--color-gray-600)]">
            Specification intelligence for building product manufacturers.
          </p>
          <p className="mt-3 max-w-xs text-sm leading-relaxed text-[var(--color-gray-400)]">
            <a href="mailto:hello@specindex.ai" className="hover:text-[var(--color-ink)]">
              hello@specindex.ai
            </a>
          </p>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-[var(--color-ink)]">Product</h3>
          <ul className="mt-4 space-y-2.5">
            {product.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="text-sm text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-[var(--color-ink)]">Company</h3>
          <ul className="mt-4 space-y-2.5">
            {company.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="text-sm text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-[var(--color-ink)]">Data &amp; Coverage</h3>
          <p className="mt-4 text-sm leading-relaxed text-[var(--color-gray-600)]">
            Commercial projects in all 50 states, filterable by state and county.
          </p>
          <ul className="mt-4 space-y-2.5">
            <li>
              <Link
                href="/projects/"
                className="text-sm text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
              >
                Search the index
              </Link>
            </li>
            <li>
              <Link
                href="/about/"
                className="text-sm text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
              >
                How we source data
              </Link>
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t border-[var(--color-border)]">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-5 py-4 md:px-8">
          <p className="text-xs text-[var(--color-gray-400)]">
            © {new Date().getFullYear()} SpecIndex. Verify before bidding or specifying.
          </p>
          <p className="text-xs text-[var(--color-gray-400)]">
            🟢 Pipeline live · No plan-room resale
          </p>
        </div>
      </div>
    </footer>
  );
}
