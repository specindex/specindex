"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { FIREBASE_AUTH_ENABLED, useFirebaseAuth } from "@/components/FirebaseAuthProvider";
import { useDemoModal } from "@/components/marketing/DemoModal";

// "Projects" deliberately excluded -- /projects/ now requires sign-in
// (ProjectsGate), so it's not a destination to invite anonymous visitors
// into from the main nav. Still reachable via the hero/feature CTAs, which
// correctly land on the sign-in wall instead of a 404.
const MARKETING_NAV = [
  { href: "/product/", label: "Product" },
  { href: "/visibility/", label: "Visibility" },
  { href: "/reporting/", label: "Reporting" },
  { href: "/how-it-works/", label: "How It Works" },
  { href: "/pricing/", label: "Pricing" },
  { href: "/about/", label: "About" },
];

// Signed-in visitors already have access -- the marketing nav (Pricing,
// How It Works, About) stops being relevant and swaps to the app surfaces
// themselves. No dedicated "Account" link or page exists yet -- Firebase
// Auth alone has no account-management UI to link to (unlike Clerk's
// <UserButton>), so UserMenu below is just avatar + sign-out for now.
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

// Only ever mounted when FIREBASE_AUTH_ENABLED -- useFirebaseAuth() throws
// without a <FirebaseAuthProvider> ancestor, so the whole auth-aware subtree
// (this and AuthAwareActions below) must not mount at all when Firebase
// Auth isn't configured, rather than mount and error.
function AuthAwareNav({ pathname, mobile }: { pathname: string | null; mobile?: boolean }) {
  const { isSignedIn } = useFirebaseAuth();
  const items = isSignedIn ? APP_NAV : MARKETING_NAV;
  return mobile ? (
    <MobileNavLinks items={items} pathname={pathname} />
  ) : (
    <DesktopNavLinks items={items} pathname={pathname} />
  );
}

// Firebase ships no prebuilt account-menu component (unlike Clerk's
// <UserButton>), so this is a minimal hand-rolled equivalent: avatar (or an
// initial-letter fallback when the sign-in provider didn't return a photo)
// plus a plain sign-out action -- no dropdown/"Manage account" surface,
// since Firebase Auth alone has no account-management page to link to.
function UserMenu() {
  const { user, signOut } = useFirebaseAuth();
  const label = user?.displayName ?? user?.email ?? "Account";
  return (
    <div className="flex items-center gap-2">
      {user?.photoURL ? (
        // eslint-disable-next-line @next/next/no-img-element -- external provider avatar URL, not a local asset
        <img src={user.photoURL} alt="" className="h-7 w-7 rounded-full" referrerPolicy="no-referrer" />
      ) : (
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--color-green-light)] text-xs font-semibold text-[var(--color-green)]">
          {label.charAt(0).toUpperCase()}
        </span>
      )}
      <button
        type="button"
        onClick={() => signOut()}
        className="text-sm text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
      >
        Sign out
      </button>
    </div>
  );
}

function AuthAwareActions({ mobile }: { mobile?: boolean }) {
  const size = mobile ? "w-full text-center" : "hidden sm:inline-flex";
  const { openDemoModal } = useDemoModal();
  const { isSignedIn, signIn } = useFirebaseAuth();
  if (isSignedIn) return <UserMenu />;
  return (
    <>
      <button type="button" onClick={() => signIn()} className={`btn btn-outline ${size}`}>
        Log In
      </button>
      <button type="button" onClick={() => openDemoModal()} className={`btn btn-demo ${size}`}>
        Request Demo
      </button>
    </>
  );
}

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const { openDemoModal } = useDemoModal();

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
          {FIREBASE_AUTH_ENABLED ? (
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
          {FIREBASE_AUTH_ENABLED ? (
            <AuthAwareActions />
          ) : (
            <button type="button" onClick={() => openDemoModal()} className="btn btn-demo hidden sm:inline-flex">
              Request Demo
            </button>
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
            {FIREBASE_AUTH_ENABLED ? (
              <AuthAwareNav pathname={pathname} mobile />
            ) : (
              <MobileNavLinks items={MARKETING_NAV} pathname={pathname} />
            )}
            {FIREBASE_AUTH_ENABLED ? (
              <div className="mt-4 flex flex-col gap-2">
                <AuthAwareActions mobile />
              </div>
            ) : (
              <button type="button" onClick={() => openDemoModal()} className="btn btn-demo mt-4 w-full text-center">
                Request Demo
              </button>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}
