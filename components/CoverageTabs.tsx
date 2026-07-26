"use client";

import { useState } from "react";
import type {
  CoverageEntry,
  CoverageInsights as CoverageInsightsData,
  StateQuality as StateQualityData,
} from "@/lib/coverage";
import { CoverageTable } from "./CoverageTable";
import { CoverageInsights } from "./CoverageInsights";
import { StateQuality } from "./StateQuality";

type Props = {
  coverage: CoverageEntry[];
  insights: CoverageInsightsData;
  quality: StateQualityData[];
};

const TABS = [
  { key: "insights", label: "Insights" },
  { key: "county", label: "By County" },
  { key: "quality", label: "Quality" },
] as const;

type Tab = (typeof TABS)[number]["key"];

export function CoverageTabs({ coverage, insights, quality }: Props) {
  const [tab, setTab] = useState<Tab>("insights");

  return (
    <div>
      <div className="mb-6 flex gap-1 border-b border-[var(--color-border)]">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium ${
              tab === t.key
                ? "border-b-2 border-[var(--color-green)] text-[var(--color-ink)]"
                : "text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "insights" && <CoverageInsights insights={insights} />}
      {tab === "county" && <CoverageTable coverage={coverage} />}
      {tab === "quality" && <StateQuality quality={quality} />}
    </div>
  );
}
