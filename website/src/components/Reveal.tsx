"use client";

import { motion } from "framer-motion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";

type RevealProps = {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  as?: "div" | "li";
};

/** A gentle fade-and-rise as content scrolls into view. Appears at once under reduced motion. */
export function Reveal({ children, className, delay = 0, as = "div" }: RevealProps) {
  const reduce = usePrefersReducedMotion();
  const Comp = as === "li" ? motion.li : motion.div;
  const shown = { opacity: 1, y: 0 };
  // The element stays the same either way, so switching never remounts what's inside.
  const play = reduce
    ? { animate: shown, transition: { duration: 0 } }
    : {
        whileInView: shown,
        viewport: { once: true, margin: "0px 0px -60px 0px" },
        transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] as const, delay },
      };
  return (
    <Comp className={className} initial={{ opacity: 0, y: 18 }} {...play}>
      {children}
    </Comp>
  );
}
