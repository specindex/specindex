"use client";

import { useState } from "react";

type FaqItem = { q: string; a: string };

export function FAQ({ items }: { items: FaqItem[] }) {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section className="bg-white">
      <div className="mx-auto max-w-3xl px-5 py-20 md:px-8">
        <h2 className="text-center text-section">Frequently Asked Questions</h2>
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
