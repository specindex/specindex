"use client";

import { useState } from "react";
import type { CoverageEntry, CoverageInsights as CoverageInsightsData } from "@/lib/coverage";
import { CoverageTable } from "./CoverageTable";
import { CoverageInsights } from "./CoverageInsights";

type Props = {
  coverage: CoverageEntry[];
  insights: CoverageInsightsData;
};

export function CoverageTabs({ coverage, insights }: Props) {
  const [tab, setTab] = useState<"insights" | "county">("insights");

  return (
    <div>
      <div className="mb-6 flex gap-1 border-b border-[var(--color-border)]">
        <button
          type="button"
          onClick={() => setTab("insights")}
          className={`px-4 py-2.5 text-sm font-medium ${
            tab === "insights"
              ? "border-b-2 border-[var(--color-green)] text-[var(--color-ink)]"
              : "text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
          }`}
        >
          Insights
        </button>
        <button
          type="button"
          onClick={() => setTab("county")}
          className={`px-4 py-2.5 text-sm font-medium ${
            tab === "county"
              ? "border-b-2 border-[var(--color-green)] text-[var(--color-ink)]"
              : "text-[var(--color-gray-600)] hover:text-[var(--color-ink)]"
          }`}
        >
          By County
        </button>
      </div>
      {tab === "insights" ? (
        <CoverageInsights insights={insights} />
      ) : (
        <CoverageTable coverage={coverage} />
      )}
    </div>
  );
}
