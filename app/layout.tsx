import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { FirebaseAuthProvider } from "@/components/FirebaseAuthProvider";
import { PostHogProvider } from "@/components/PostHogProvider";
import { DemoModalProvider } from "@/components/marketing/DemoModal";
import { SiteHeader } from "@/components/SiteHeader";
import { SiteFooter } from "@/components/SiteFooter";

// Geist system (body/headings + data/IDs), replacing Inter/JetBrains
// Mono/Space Grotesk site-wide -- geist/font ships as next/font/local under
// the hood (Vercel's own package, not Google Fonts), so no `subsets` or
// `display` config here; it's pre-optimized static font files.

export const metadata: Metadata = {
  title: {
    default: "SpecIndex · Specification intelligence for building product manufacturers",
    template: "%s · SpecIndex",
  },
  description:
    "Commercial construction projects nationwide, indexed by stage and product category, so building product manufacturers can tell which specs are still open.",
  metadataBase: new URL("https://specindex.ai"),
  openGraph: {
    title: "SpecIndex · Specification intelligence for building product manufacturers",
    description:
      "Your product gets chosen long before anyone asks for a quote. SpecIndex shows which commercial projects are still early enough to influence.",
    url: "https://specindex.ai",
    siteName: "SpecIndex",
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "SpecIndex",
    description:
      "Commercial projects nationwide, indexed by stage and product category, for building product manufacturers.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        {/* FirebaseAuthProvider wraps DemoModalProvider (not the reverse) so
            the demo-request modal can safely call useFirebaseAuth() to link
            a submission to a signed-in user (docs/PRD_SIGNUP_CRM.md Section
            2.2) -- it degrades to "no auth" internally when unconfigured,
            never throws, so nesting it outermost has no downside. */}
        <PostHogProvider />
        <FirebaseAuthProvider>
          <DemoModalProvider>
            <div className="min-h-screen flex flex-col">
              <SiteHeader />
              <main className="flex-1">{children}</main>
              <SiteFooter />
            </div>
          </DemoModalProvider>
        </FirebaseAuthProvider>
      </body>
    </html>
  );
}
