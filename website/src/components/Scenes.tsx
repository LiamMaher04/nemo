import { colors } from "@/theme/tokens";

/**
 * Small illustrated "snapshots" standing in for the photo Nemo shows.
 * TODO: replace with real captured frames from the prototype.
 */

const wood = "#C9A27E";
const wall = "#EDE5D8";

export function KeysScene() {
  return (
    <svg viewBox="0 0 240 160" className="h-full w-full" aria-hidden="true">
      <rect width="240" height="160" fill={wall} />
      <rect x="0" y="92" width="240" height="68" fill={wood} />
      <rect x="0" y="92" width="240" height="6" fill="#B48C68" />
      {/* fruit bowl */}
      <path d="M150 92 a34 18 0 0 0 68 0z" fill={colors.aqua} />
      <circle cx="170" cy="84" r="10" fill={colors.coral} />
      <circle cx="190" cy="82" r="11" fill="#E8B04B" />
      {/* keys */}
      <g transform="translate(72 112) rotate(-12)">
        <circle r="11" fill="none" stroke="#8A8F98" strokeWidth="4" />
        <rect x="8" y="-4" width="34" height="8" rx="3" fill="#B9BEC6" />
        <rect x="32" y="2" width="4" height="7" fill="#B9BEC6" />
        <rect x="24" y="2" width="4" height="5" fill="#B9BEC6" />
        <rect x="-4" y="8" width="10" height="26" rx="4" fill={colors.navy} transform="rotate(30)" />
      </g>
      {/* "found" marker */}
      <circle cx="84" cy="114" r="34" fill="none" stroke={colors.coral} strokeWidth="4" strokeDasharray="6 6" />
    </svg>
  );
}

export function GlassesScene() {
  return (
    <svg viewBox="0 0 240 160" className="h-full w-full" aria-hidden="true">
      <rect width="240" height="160" fill={wall} />
      <rect x="20" y="20" width="200" height="130" fill="#A97F5C" />
      <rect x="28" y="28" width="184" height="54" fill="#F3ECE0" />
      <rect x="28" y="88" width="184" height="54" fill="#F3ECE0" />
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <rect key={i} x={36 + i * 14} y={38 - (i % 2) * 4} width="11" height={44 + (i % 2) * 4} fill={[colors.navy, colors.aqua, colors.coral][i % 3]} opacity="0.85" />
      ))}
      {[0, 1, 2].map((i) => (
        <rect key={i} x={150 + i * 16} y={98} width="13" height="44" fill={[colors.aqua, colors.navy, "#E8B04B"][i]} opacity="0.85" />
      ))}
      {/* glasses */}
      <g fill="none" stroke={colors.charcoal} strokeWidth="4">
        <circle cx="168" cy="66" r="13" />
        <circle cx="198" cy="66" r="13" />
        <path d="M181 64 q4 -4 4 0" />
      </g>
      <circle cx="183" cy="66" r="36" fill="none" stroke={colors.coral} strokeWidth="4" strokeDasharray="6 6" />
    </svg>
  );
}

export function RemoteScene() {
  return (
    <svg viewBox="0 0 240 160" className="h-full w-full" aria-hidden="true">
      <rect width="240" height="160" fill={wall} />
      {/* sofa */}
      <rect x="10" y="60" width="220" height="70" rx="18" fill={colors.aqua} />
      <rect x="10" y="88" width="220" height="50" rx="14" fill="#2F8A90" />
      <rect x="4" y="70" width="40" height="72" rx="16" fill="#2F8A90" />
      <rect x="196" y="70" width="40" height="72" rx="16" fill="#2F8A90" />
      <rect x="0" y="140" width="240" height="20" fill={wood} />
      {/* cushion */}
      <rect x="60" y="66" width="56" height="34" rx="10" fill={colors.cream} />
      {/* remote on the arm */}
      <g transform="translate(206 62) rotate(70)">
        <rect x="-8" y="-24" width="16" height="48" rx="6" fill={colors.charcoal} />
        <circle cx="0" cy="-14" r="3" fill={colors.coral} />
        <circle cx="0" cy="-3" r="2" fill="#888" />
        <circle cx="0" cy="5" r="2" fill="#888" />
      </g>
      <circle cx="206" cy="62" r="34" fill="none" stroke={colors.coral} strokeWidth="4" strokeDasharray="6 6" />
    </svg>
  );
}
