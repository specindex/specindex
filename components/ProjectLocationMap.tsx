"use client";

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";

type Props = {
  latitude: number | null | undefined;
  longitude: number | null | undefined;
  name: string;
};

export function ProjectLocationMap({ latitude, longitude, name }: Props) {
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
    return (
      <div className="card flex h-64 items-center justify-center p-4 text-sm text-[var(--color-gray-600)]">
        Location not yet geocoded for this project.
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
