import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "@/components/SiteHeader";
import { SiteFooter } from "@/components/SiteFooter";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

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
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body>
        <div className="min-h-screen flex flex-col">
          <SiteHeader />
          <main className="flex-1">{children}</main>
          <SiteFooter />
        </div>
      </body>
    </html>
  );
}
