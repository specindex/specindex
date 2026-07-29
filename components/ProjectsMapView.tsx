"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";
import { formatUsd } from "@/lib/format";
import { buildQuery } from "./ProjectsDashboard";

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

type MapPoint = {
  id: string;
  spx_id: string;
  name: string;
  city: string;
  county: string;
  state: string;
  latitude: number;
  longitude: number;
  status: string;
  estimated_value_usd: number | null;
  score: number;
};

export type ProjectsMapFilters = {
  territory: string[];
  status: string;
  projectType: string;
  county: string;
  category: string;
  year: string;
  hasDocuments: string;
  documentType: string;
  query: string;
  newOnly: boolean;
};

type Props = { filters: ProjectsMapFilters };

export function ProjectsMapView({ filters }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("leaflet").Map | null>(null);
  const markersRef = useRef<import("leaflet").LayerGroup | null>(null);
  const [points, setPoints] = useState<MapPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const qs = buildQuery({
      state: filters.territory.join(","),
      status: filters.status,
      project_type: filters.projectType,
      county: filters.county,
      category: filters.category,
      year: filters.year,
      has_documents:
        filters.hasDocuments === "all" ? undefined : filters.hasDocuments === "yes" ? "true" : "false",
      document_type: filters.documentType === "all" ? undefined : filters.documentType,
      q: filters.query,
      new_since_days: filters.newOnly ? 7 : undefined,
    });
    fetch(`${API_BASE}/v1/projects/map-points?${qs}`)
      .then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (!cancelled) setPoints(data.points ?? []);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load map points");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    filters.territory,
    filters.status,
    filters.projectType,
    filters.county,
    filters.category,
    filters.year,
    filters.hasDocuments,
    filters.documentType,
    filters.query,
    filters.newOnly,
  ]);

  // Leaflet is imported dynamically inside the effect, never at module top
  // level -- it touches `window` on load, which breaks Next.js's static
  // prerendering even inside a "use client" component. Same pattern as
  // ProjectLocationMap.tsx.
  useEffect(() => {
    if (!containerRef.current) return;
    let cancelled = false;

    import("leaflet").then((L) => {
      if (cancelled || !containerRef.current) return;
      if (!mapRef.current) {
        const map = L.map(containerRef.current, {
          center: [39.5, -98.35],
          zoom: 4,
        });
        mapRef.current = map;
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          maxZoom: 19,
        }).addTo(map);
        markersRef.current = L.layerGroup().addTo(map);
      }

      const group = markersRef.current!;
      group.clearLayers();

      const bounds: [number, number][] = [];
      for (const p of points) {
        bounds.push([p.latitude, p.longitude]);
        const marker = L.circleMarker([p.latitude, p.longitude], {
          radius: 6,
          weight: 1,
          color: "#166534",
          fillColor: p.score >= 70 ? "#f59e0b" : "#166534",
          fillOpacity: 0.8,
        });
        marker.bindPopup(
          `<strong>${escapeHtml(p.name)}</strong><br/>${escapeHtml(p.city)}, ${escapeHtml(p.state)}` +
            `<br/>${p.estimated_value_usd ? escapeHtml(formatUsd(p.estimated_value_usd)) : ""}` +
            `<br/><a href="/projects/${encodeURIComponent(p.id)}/">View project →</a>`
        );
        group.addLayer(marker);
      }
      if (bounds.length > 0) {
        mapRef.current!.fitBounds(bounds, { padding: [24, 24], maxZoom: 12 });
      }
    });

    return () => {
      cancelled = true;
    };
  }, [points]);

  useEffect(() => {
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <div>
      <div
        ref={containerRef}
        className="h-[32rem] w-full overflow-hidden rounded-lg border border-[var(--color-border)]"
      />
      {error && <p className="mt-2 text-sm text-red-600">Failed to load map: {error}</p>}
      {!error && (
        <p className="mt-2 text-xs text-[var(--color-gray-600)]">
          {loading ? "Loading…" : `${points.length.toLocaleString()} geocoded projects shown (of the current filter)`}
        </p>
      )}
    </div>
  );
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}
