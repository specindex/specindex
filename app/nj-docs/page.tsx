import type { Metadata } from "next";
import { NjPipelineDashboard } from "@/components/NjPipelineDashboard";

export const metadata: Metadata = {
  title: "NJ Pipeline",
  description:
    "New Jersey commercial permits from Socrata DCA, then Gemini Flash document gather and Claude Sonnet audit.",
  robots: { index: false, follow: false },
};

export default function NjDocsPage() {
  return (
    <div className="bg-[var(--color-bg)]">
      <div className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl px-5 py-12 md:px-8 md:py-16">
          <p className="text-eyebrow">New Jersey test</p>
          <h1 className="mt-3 text-hero">Socrata, then Flash, then Sonnet</h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--color-gray-600)]">
            Deterministic NJ DCA permits first. Gemini Flash gathers public construction
            documents at high recall. Claude Sonnet audits and dedupes for precision.
            Counts on this page are computed from the latest pipeline run, not invented.
          </p>
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <NjPipelineDashboard />
      </div>
    </div>
  );
}
