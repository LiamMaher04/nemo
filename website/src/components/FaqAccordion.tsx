"use client";

import { useId, useState } from "react";

type Faq = { q: string; a: string[] };

/** Accessible accordion: real buttons, aria-expanded, aria-controls, labelled regions. */
export function FaqAccordion({ items }: { items: Faq[] }) {
  const [open, setOpen] = useState<number | null>(0);
  const base = useId();

  return (
    <div className="border-b border-navy/15">
      {items.map((item, i) => {
        const isOpen = open === i;
        const btnId = `${base}-btn-${i}`;
        const panelId = `${base}-panel-${i}`;
        return (
          <div key={item.q} className="rule">
            <h3 className="text-xl">
              <button
                id={btnId}
                type="button"
                aria-expanded={isOpen}
                aria-controls={panelId}
                onClick={() => setOpen(isOpen ? null : i)}
                className="group flex min-h-16 w-full items-center justify-between gap-6 py-6 text-left font-heading font-semibold text-navy"
              >
                <span className="underline-offset-[6px] group-hover:underline">{item.q}</span>
                {/* plus that turns into a minus */}
                <span aria-hidden="true" className="relative h-5 w-5 shrink-0">
                  <span className="absolute left-0 top-1/2 h-0.5 w-5 -translate-y-1/2 rounded bg-navy" />
                  <span
                    className={`absolute left-1/2 top-0 h-5 w-0.5 -translate-x-1/2 rounded bg-navy transition-transform duration-300 ${
                      isOpen ? "scale-y-0" : ""
                    }`}
                  />
                </span>
              </button>
            </h3>
            <div id={panelId} role="region" aria-labelledby={btnId} hidden={!isOpen} className="max-w-2xl space-y-4 pb-8 text-lg">
              {item.a.map((p) => (
                <p key={p}>{p}</p>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
