"use client";

import { useState } from "react";

type FaqItem = { q: string; a: string };

// FAQPage JSON-LD from the exact same {q, a} content already rendered
// below -- no new copy, just making content that already exists visible
// to rich-result surfaces (AI Overviews, People-Also-Ask). Flagged as the
// single highest-leverage SEO fix in docs/architecture-2026/03-growth.md
// (zero marketing pages carry structured data today; only the per-project
// detail pages do). Same dangerouslySetInnerHTML script-tag pattern
// app/projects/[id]/page.tsx already uses for its own JSON-LD.
function faqJsonLd(items: FaqItem[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: { "@type": "Answer", text: item.a },
    })),
  };
}

export function FAQ({
  items,
  eyebrow,
  heading = "Frequently Asked Questions",
}: {
  items: FaqItem[];
  eyebrow?: string;
  heading?: string;
}) {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section className="bg-white">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd(items)) }}
      />
      <div className="mx-auto max-w-3xl px-5 py-20 md:px-8">
        {eyebrow && <p className="section-label text-center">{eyebrow}</p>}
        <h2 className="mt-2 text-center text-section">{heading}</h2>
        <ul className="mt-10 divide-y divide-[var(--color-border)]">
          {items.map((item, i) => (
            <li key={item.q}>
              <button
                type="button"
                onClick={() => setOpen(open === i ? null : i)}
                className="flex w-full items-start justify-between gap-4 py-5 text-left"
              >
                <span className="font-semibold text-[var(--color-ink)]">
                  Q. {item.q}
                </span>
                <span className="text-[var(--color-gray-400)]">{open === i ? "−" : "+"}</span>
              </button>
              {open === i && (
                <p className="pb-5 text-sm leading-relaxed text-[var(--color-gray-600)]">
                  {item.a}
                </p>
              )}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
