"use client";

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";

type Props = {
  latitude: number | null | undefined;
  longitude: number | null | undefined;
  name: string;
  city?: string;
  county?: string;
  state?: string;
};

export function ProjectLocationMap({ latitude, longitude, name, city, county, state }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("leaflet").Map | null>(null);

  useEffect(() => {
    if (!containerRef.current || latitude == null || longitude == null) return;
    if (mapRef.current) return;
    let cancelled = false;

    // Leaflet touches `window` at module load time, which breaks Next.js's
    // static prerendering even inside a "use client" component (the app
    // still renders it once server-side for the initial HTML). Importing
    // it only here, inside an effect that only ever runs in the browser,
    // avoids that entirely.
    import("leaflet").then((L) => {
      if (cancelled || !containerRef.current || mapRef.current) return;
      const map = L.map(containerRef.current, {
        center: [latitude, longitude],
        zoom: 15,
        scrollWheelZoom: false,
      });
      mapRef.current = map;

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(map);

      L.marker([latitude, longitude]).addTo(map).bindPopup(name);
    });

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [latitude, longitude, name]);

  if (latitude == null || longitude == null) {
    const regionLabel = [city, county ? `${county} County` : null, state]
      .filter(Boolean)
      .join(", ");
    return (
      <div className="card flex h-64 flex-col items-center justify-center gap-2 p-4 text-center">
        <span className="rounded-full bg-[var(--color-amber)]/10 px-2.5 py-1 text-xs font-medium text-[var(--color-amber)]">
          📍 Regional location pending
        </span>
        {regionLabel && (
          <p className="text-sm font-medium text-[var(--color-ink)]">{regionLabel}</p>
        )}
        <p className="max-w-xs text-xs text-[var(--color-gray-600)]">
          Exact coordinates for this project haven&apos;t been geocoded yet.
        </p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="h-64 w-full overflow-hidden rounded-lg border border-[var(--color-border)]"
    />
  );
}
