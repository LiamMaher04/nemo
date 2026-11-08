"use client";

import { useId } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { colors } from "@/theme/tokens";

const wall = { fill: "none", stroke: colors.navy, strokeWidth: 4, strokeLinecap: "round" as const };
const furniture = { fill: "none", stroke: colors.navy, strokeOpacity: 0.35, strokeWidth: 2, strokeLinejoin: "round" as const };

// The walk: in through the front door, then bedroom, kitchen, living room, bathroom.
const WALK =
  "M85 372 C 85 330, 120 300, 140 290 C 160 280, 140 230, 135 200 C 130 170, 120 130, 140 115 C 170 95, 230 112, 260 115 C 300 118, 350 100, 380 112 C 400 125, 378 170, 375 200 C 372 240, 360 270, 380 290";

// Where Nemo hears each room's name, in walking order.
const rooms = [
  { name: "Bedroom", x: 140, y: 290 },
  { name: "Kitchen", x: 140, y: 115 },
  { name: "Living room", x: 380, y: 112 },
  { name: "Bathroom", x: 380, y: 290 },
];

/** A spoken room name, in a small speech bubble above the spot. */
function Bubble({ name, x, y }: { name: string; x: number; y: number }) {
  const label = `“${name}.”`;
  const w = label.length * 10.5 + 28;
  const top = y - 62;
  return (
    <g>
      <rect x={x - w / 2} y={top} width={w} height={36} rx={18} fill={colors.cream} stroke={colors.navy} strokeWidth={2} />
      <path d={`M${x - 7} ${top + 35} L${x} ${top + 46} L${x + 7} ${top + 35}`} fill={colors.cream} stroke={colors.navy} strokeWidth={2} strokeLinejoin="round" />
      <path d={`M${x - 8} ${top + 34.5} H${x + 8}`} stroke={colors.cream} strokeWidth={3} />
      <text x={x} y={top + 24} textAnchor="middle" className="font-heading" fontSize={18} fontWeight={600} fill={colors.navy}>
        {label}
      </text>
    </g>
  );
}

/**
 * A floor plan of a home with the one-time setup walk drawn through it:
 * a dotted path room by room, and the name said out loud in each room.
 */
export function RoomMap({ className }: { className?: string }) {
  const reduce = useReducedMotion();
  const maskId = `walk-${useId().replace(/:/g, "")}`;
  const draw = reduce
    ? {}
    : {
        initial: { pathLength: 0 },
        whileInView: { pathLength: 1 },
        viewport: { once: true, margin: "0px 0px -80px 0px" },
        transition: { duration: 2.4, ease: [0.45, 0, 0.25, 1] as const },
      };

  return (
    <svg viewBox="0 0 520 400" className={className} aria-hidden="true">
      {/* Outer walls, with the front door gap at the bottom left */}
      <path d="M60 380 H20 V20 H500 V380 H110" {...wall} />
      {/* Inner walls, with doorways */}
      <path d="M260 20 V90 M260 140 V260 M260 310 V380" {...wall} />
      <path d="M20 200 H110 M160 200 H260 M260 200 H350 M400 200 H500" {...wall} />

      {/* A few hints of furniture */}
      <rect x="34" y="34" width="150" height="26" rx="4" {...furniture} />
      <circle cx="215" cy="160" r="16" {...furniture} />
      <rect x="400" y="140" width="84" height="40" rx="10" {...furniture} />
      <rect x="36" y="276" width="70" height="92" rx="8" {...furniture} />
      <path d="M36 300 H106" {...furniture} />
      <rect x="420" y="300" width="64" height="62" rx="18" {...furniture} />

      {/* The walk: a dotted line, revealed along its length by an animated mask */}
      <mask id={maskId} maskUnits="userSpaceOnUse" x="0" y="0" width="520" height="400">
        <motion.path d={WALK} fill="none" stroke="#fff" strokeWidth={14} strokeLinecap="round" {...draw} />
      </mask>
      <path
        d={WALK}
        fill="none"
        stroke={colors.aqua}
        strokeWidth={3.5}
        strokeLinecap="round"
        strokeDasharray="1 9"
        mask={`url(#${maskId})`}
      />

      {/* The stops, the names, and Nemo at the end of the walk */}
      {rooms.map((r) => (
        <circle key={r.name} cx={r.x} cy={r.y} r={7} fill={colors.cream} stroke={colors.aqua} strokeWidth={3} />
      ))}
      {rooms.map((r) => (
        <Bubble key={r.name} {...r} />
      ))}
      <circle cx="380" cy="290" r="9" fill={colors.coral} />
    </svg>
  );
}
