import type { Metadata } from "next";
import { MapDashboard } from "@/components/MapDashboard";

export const metadata: Metadata = {
  title: "Map",
  robots: { index: false, follow: false },
};

export default function MapPage() {
  return (
    <div className="bg-[var(--color-bg)]">
      <div className="border-b border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl px-5 py-12 md:px-8 md:py-16">
          <p className="text-eyebrow">Internal</p>
          <h1 className="mt-3 text-hero">Project map</h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-[var(--color-gray-600)]">
            Every project with real coordinates (currently ArcGIS-sourced records; most
            other sources don&apos;t provide geocoding yet). Filter by county or city,
            click a pin for the project. Not linked from public nav.
          </p>
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-12">
        <MapDashboard />
      </div>
    </div>
  );
}
