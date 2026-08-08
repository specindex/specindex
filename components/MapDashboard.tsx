"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

// Mapbox GL paint properties can't read CSS custom properties, so these
// mirror --color-green / --color-amber / --color-white from app/globals.css.
const MAP_COLOR_GREEN = "#166534";
const MAP_COLOR_AMBER = "#f59e0b";
const MAP_COLOR_WHITE = "#ffffff";

const API_BASE = "https://specindex-api-gmm6irqe4q-uc.a.run.app";

type MapPoint = {
  id: string;
  name: string;
  state: string;
  county: string;
  city: string;
  latitude: number;
  longitude: number;
};

export function MapDashboard() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const [points, setPoints] = useState<MapPoint[]>([]);
  const [county, setCounty] = useState<string>("all");
  const [city, setCity] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const tokenRes = await fetch(`${API_BASE}/v1/ops/mapbox-token`);
        if (!tokenRes.ok) {
          throw new Error(
            tokenRes.status === 429
              ? "Map quota exceeded for this month"
              : `Token request failed: ${tokenRes.status}`,
          );
        }
        const { token } = await tokenRes.json();
        if (cancelled) return;
        mapboxgl.accessToken = token;

        const pointsRes = await fetch(`${API_BASE}/v1/ops/map-points`);
        const data = await pointsRes.json();
        if (cancelled) return;
        setPoints(data.points ?? []);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const counties = useMemo(
    () => Array.from(new Set(points.map((p) => p.county).filter(Boolean))).sort(),
    [points],
  );
  const cities = useMemo(
    () => Array.from(new Set(points.map((p) => p.city).filter(Boolean))).sort(),
    [points],
  );
  const filtered = useMemo(
    () =>
      points.filter(
        (p) => (county === "all" || p.county === county) && (city === "all" || p.city === city),
      ),
    [points, county, city],
  );

  useEffect(() => {
    if (loading || error || !mapContainer.current || mapRef.current) return;
    const map = new mapboxgl.Map({
      container: mapContainer.current,
      style: "mapbox://styles/mapbox/light-v11",
      center: [-82, 35],
      zoom: 6,
    });
    mapRef.current = map;
  }, [loading, error]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    function render(map: mapboxgl.Map) {
      const geojson = {
        type: "FeatureCollection" as const,
        features: filtered.map((p) => ({
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: [p.longitude, p.latitude] },
          properties: { id: p.id, name: p.name },
        })),
      };

      if (map.getSource("projects")) {
        (map.getSource("projects") as mapboxgl.GeoJSONSource).setData(geojson);
        return;
      }

      map.addSource("projects", {
        type: "geojson",
        data: geojson,
        cluster: true,
        clusterMaxZoom: 12,
        clusterRadius: 40,
      });
      map.addLayer({
        id: "clusters",
        type: "circle",
        source: "projects",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": MAP_COLOR_GREEN,
          "circle-radius": ["step", ["get", "point_count"], 16, 10, 22, 50, 28],
          "circle-opacity": 0.85,
        },
      });
      map.addLayer({
        id: "cluster-count",
        type: "symbol",
        source: "projects",
        filter: ["has", "point_count"],
        layout: { "text-field": "{point_count_abbreviated}", "text-size": 12 },
        paint: { "text-color": MAP_COLOR_WHITE },
      });
      map.addLayer({
        id: "unclustered-point",
        type: "circle",
        source: "projects",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": MAP_COLOR_AMBER,
          "circle-radius": 6,
          "circle-stroke-width": 1,
          "circle-stroke-color": MAP_COLOR_WHITE,
        },
      });

      map.on("click", "unclustered-point", (e) => {
        const f = e.features?.[0];
        if (!f || f.geometry.type !== "Point") return;
        const [lng, lat] = f.geometry.coordinates as [number, number];
        new mapboxgl.Popup()
          .setLngLat([lng, lat])
          .setHTML(
            `<a href="/project/${f.properties?.id}/" style="font-weight:600">${f.properties?.name}</a>`,
          )
          .addTo(map);
      });
      map.on("click", "clusters", (e) => {
        const f = e.features?.[0];
        if (!f || f.geometry.type !== "Point") return;
        const center = f.geometry.coordinates as [number, number];
        const source = map.getSource("projects") as mapboxgl.GeoJSONSource;
        source.getClusterExpansionZoom(f.properties?.cluster_id, (err, zoom) => {
          if (err) return;
          map.easeTo({ center, zoom: zoom ?? 10 });
        });
      });
    }

    if (map.isStyleLoaded()) render(map);
    else map.once("load", () => render(map));
  }, [filtered]);

  if (loading) {
    return <p className="text-sm text-[var(--color-gray-600)]">Loading map…</p>;
  }
  if (error) {
    return <p className="text-sm text-red-600">Failed to load map: {error}</p>;
  }

  return (
    <div>
      <div className="card p-4 md:p-5">
        <p className="text-sm text-[var(--color-gray-600)]">
          {filtered.length} of {points.length} projects have real coordinates (from ArcGIS
          sources; most sources don&apos;t provide coordinates yet — see the ops dashboard for
          coverage by state).
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <select
            value={county}
            onChange={(e) => setCounty(e.target.value)}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="all">All counties</option>
            {counties.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            value={city}
            onChange={(e) => setCity(e.target.value)}
            className="rounded-md border border-[var(--color-border)] bg-white px-3 py-2 text-sm"
          >
            <option value="all">All cities</option>
            {cities.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div ref={mapContainer} className="mt-6 h-[600px] w-full rounded-lg border border-[var(--color-border)]" />
    </div>
  );
}
