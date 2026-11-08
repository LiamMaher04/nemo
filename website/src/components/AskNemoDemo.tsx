"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { GlassesScene, KeysScene, RemoteScene } from "./Scenes";

const conversations = [
  {
    item: "keys",
    label: "Keys",
    question: "Where are my keys?",
    answer: "I last saw your keys on the kitchen table, next to the fruit bowl. That was about twenty minutes ago.",
    Scene: KeysScene,
    alt: "Snapshot of a kitchen table with a set of keys beside a bowl of fruit, circled.",
  },
  {
    item: "glasses",
    label: "Glasses",
    question: "Have you seen my glasses?",
    answer: "Your glasses are on the top shelf of the bookcase in the living room. You set them down this morning.",
    Scene: GlassesScene,
    alt: "Snapshot of a bookcase with a pair of reading glasses on the top shelf, circled.",
  },
  {
    item: "remote",
    label: "Remote",
    question: "Where did I put the remote?",
    answer: "The remote is on the right arm of the sofa. I saw it there about an hour ago.",
    Scene: RemoteScene,
    alt: "Snapshot of a sofa with the TV remote resting on its right arm, circled.",
  },
];

/** A simulated "Ask Nemo" exchange: pick a question, see Nemo's spoken answer and photo. */
export function AskNemoDemo() {
  const [index, setIndex] = useState(0);
  const convo = conversations[index];

  return (
    <div>
      <div role="group" aria-label="Choose what to ask about" className="flex flex-wrap gap-2">
        {conversations.map((c, i) => (
          <button
            key={c.item}
            type="button"
            aria-pressed={i === index}
            onClick={() => setIndex(i)}
            className={`min-h-12 rounded-full px-5 font-heading font-semibold transition-colors ${
              i === index ? "bg-navy text-cream" : "text-navy ring-1 ring-inset ring-navy/30 hover:bg-navy/[0.06]"
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      <div className="mt-6 overflow-hidden rounded-2xl bg-cream ring-1 ring-navy/15">
        <div aria-live="polite">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={convo.item}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.3, ease: "easeOut" }}
            >
              <div className="p-6 sm:p-8">
                <p className="text-base font-medium text-navy">You asked</p>
                <p className="mt-1 font-heading text-xl font-semibold text-navy">&ldquo;{convo.question}&rdquo;</p>

                <div className="mt-6 flex items-center gap-3">
                  <span className="flex h-6 items-end gap-[3px]" aria-hidden="true">
                    {[10, 18, 24, 14, 20, 9, 16].map((h, i) => (
                      <span key={i} className="w-[3px] rounded-full bg-aqua" style={{ height: h }} />
                    ))}
                  </span>
                  <p className="text-base font-medium text-navy">Nemo says</p>
                </div>
                <p className="mt-2 text-xl leading-relaxed">&ldquo;{convo.answer}&rdquo;</p>
              </div>
              <figure>
                <div className="aspect-[3/2] w-full border-t border-navy/15" role="img" aria-label={convo.alt}>
                  <convo.Scene />
                </div>
                <figcaption className="border-t border-navy/15 px-6 py-3 text-base sm:px-8">
                  Where I last saw your {convo.item}
                </figcaption>
              </figure>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
