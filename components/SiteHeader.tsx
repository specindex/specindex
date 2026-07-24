"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const nav = [
  { href: "/product/", label: "Product" },
  { href: "/how-it-works/", label: "How It Works" },
  { href: "/pricing/", label: "Pricing" },
  { href: "/about/", label: "About" },
];

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-white/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-3.5 md:px-8">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-[var(--color-green)] text-sm font-bold text-white">
            S
          </span>
          <span className="text-lg font-semibold tracking-tight text-[var(--color-ink)]">
            SpecIndex
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {nav.map((link) => {
            const active =
              pathname === link.href || pathname.startsWith(link.href.slice(0, -1));
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-md px-3 py-2 text-sm font-medium transition ${
                  active
                    ? "text-[var(--color-ink)]"
                    : "text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          <a
            href="mailto:hello@specindex.ai"
            className="hidden text-sm text-[var(--color-gray-600)] hover:text-[var(--color-ink)] lg:inline"
          >
            hello@specindex.ai
          </a>
          <Link href="/projects/" className="btn btn-primary">
            Get a Demo
          </Link>
        </div>
      </div>
    </header>
  );
}
