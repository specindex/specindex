"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { CLERK_ENABLED } from "@/components/ClerkProviders";
import { SignedIn, SignedOut, SignInButton, UserButton, useAuth } from "@clerk/clerk-react";

const MARKETING_NAV = [
  { href: "/product/", label: "Product" },
  { href: "/projects/", label: "Projects" },
  { href: "/visibility/", label: "Visibility" },
  { href: "/reporting/", label: "Reporting" },
  { href: "/how-it-works/", label: "How It Works" },
  { href: "/pricing/", label: "Pricing" },
  { href: "/about/", label: "About" },
];

// Signed-in visitors already have access -- the marketing nav (Pricing,
// How It Works, About) stops being relevant and swaps to the app surfaces
// themselves. No dedicated "Account" link: <UserButton>'s own menu already
// includes "Manage account", so it doubles as that surface.
const APP_NAV = [
  { href: "/projects/", label: "Projects" },
  { href: "/visibility/", label: "Visibility" },
  { href: "/reporting/", label: "Reporting" },
];

type NavLink = { href: string; label: string };

function isActive(pathname: string | null, href: string) {
  return pathname === href || (href !== "/" && !!pathname?.startsWith(href.slice(0, -1)));
}

function DesktopNavLinks({ items, pathname }: { items: NavLink[]; pathname: string | null }) {
  return (
    <>
      {items.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className={`rounded-md px-2.5 py-2 text-sm font-medium transition ${
            isActive(pathname, link.href)
              ? "text-[var(--color-ink)]"
              : "text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
          }`}
        >
          {link.label}
        </Link>
      ))}
    </>
  );
}

function MobileNavLinks({ items, pathname }: { items: NavLink[]; pathname: string | null }) {
  return (
    <>
      {items.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className={`rounded-md px-3 py-3 text-base font-medium ${
            isActive(pathname, link.href)
              ? "bg-[var(--color-gray-100)] text-[var(--color-ink)]"
              : "text-[var(--color-gray-600)]"
          }`}
        >
          {link.label}
        </Link>
      ))}
    </>
  );
}

// Only ever mounted when CLERK_ENABLED -- useAuth() throws without a
// <ClerkProvider> ancestor, so the whole auth-aware subtree (this and
// AuthAwareActions below) must not mount at all when Clerk isn't
// configured, rather than mount and error.
function AuthAwareNav({ pathname, mobile }: { pathname: string | null; mobile?: boolean }) {
  const { isSignedIn } = useAuth();
  const items = isSignedIn ? APP_NAV : MARKETING_NAV;
  return mobile ? (
    <MobileNavLinks items={items} pathname={pathname} />
  ) : (
    <DesktopNavLinks items={items} pathname={pathname} />
  );
}

function AuthAwareActions({ mobile }: { mobile?: boolean }) {
  const size = mobile ? "w-full text-center" : "hidden sm:inline-flex";
  return (
    <>
      <SignedOut>
        <SignInButton mode="modal">
          <button type="button" className={`btn btn-outline ${size}`}>
            Log In
          </button>
        </SignInButton>
        <Link href="/#demo" className={`btn btn-demo ${size}`}>
          Request Demo
        </Link>
      </SignedOut>
      <SignedIn>
        <UserButton afterSignOutUrl="/" />
      </SignedIn>
    </>
  );
}

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
          <Logo size={28} />
          <span className="text-lg font-semibold tracking-tight text-[var(--color-ink)]">
            SpecIndex
          </span>
        </Link>

        <nav className="hidden items-center gap-0.5 lg:flex">
          {CLERK_ENABLED ? (
            <AuthAwareNav pathname={pathname} />
          ) : (
            <DesktopNavLinks items={MARKETING_NAV} pathname={pathname} />
          )}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          <a
            href="mailto:hello@specindex.ai"
            className="hidden text-sm text-[var(--color-gray-600)] hover:text-[var(--color-ink)] xl:inline"
          >
            hello@specindex.ai
          </a>
          {CLERK_ENABLED ? (
            <AuthAwareActions />
          ) : (
            <Link href="/#demo" className="btn btn-demo hidden sm:inline-flex">
              Request Demo
            </Link>
          )}
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
            {CLERK_ENABLED ? (
              <AuthAwareNav pathname={pathname} mobile />
            ) : (
              <MobileNavLinks items={MARKETING_NAV} pathname={pathname} />
            )}
            {CLERK_ENABLED ? (
              <div className="mt-4 flex flex-col gap-2">
                <AuthAwareActions mobile />
              </div>
            ) : (
              <Link href="/#demo" className="btn btn-demo mt-4 w-full text-center">
                Request Demo
              </Link>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}
