"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const nav = [
  { href: "/product/", label: "Product" },
  { href: "/projects/", label: "Projects" },
  { href: "/visibility/", label: "Visibility" },
  { href: "/how-it-works/", label: "How It Works" },
  { href: "/pricing/", label: "Pricing" },
  { href: "/about/", label: "About" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

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

        <nav className="hidden items-center gap-0.5 lg:flex">
          {nav.map((link) => {
            const active =
              pathname === link.href ||
              (link.href !== "/" && pathname.startsWith(link.href.slice(0, -1)));
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-md px-2.5 py-2 text-sm font-medium transition ${
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

        <div className="flex items-center gap-2 sm:gap-3">
          <a
            href="mailto:hello@specindex.ai"
            className="hidden text-sm text-[var(--color-gray-600)] hover:text-[var(--color-ink)] xl:inline"
          >
            hello@specindex.ai
          </a>
          <Link href="/#demo" className="btn btn-primary hidden sm:inline-flex">
            Request Demo
          </Link>
          <button
            type="button"
            aria-expanded={open}
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((v) => !v)}
            className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-[var(--color-border)] text-[var(--color-ink)] lg:hidden"
          >
            <span className="sr-only">Menu</span>
            {open ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path
                  d="M6 6l12 12M18 6L6 18"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path
                  d="M4 7h16M4 12h16M4 17h16"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            )}
          </button>
        </div>
      </div>

      {open && (
        <div className="border-t border-[var(--color-border)] bg-white lg:hidden">
          <nav className="mx-auto flex max-w-6xl flex-col px-5 py-4">
            {nav.map((link) => {
              const active =
                pathname === link.href ||
                (link.href !== "/" && pathname.startsWith(link.href.slice(0, -1)));
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-md px-3 py-3 text-base font-medium ${
                    active
                      ? "bg-[var(--color-gray-100)] text-[var(--color-ink)]"
                      : "text-[var(--color-gray-600)]"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
            <Link href="/#demo" className="btn btn-primary mt-4 w-full">
              Request Demo
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}
