import { colors } from "@/theme/tokens";

/**
 * Front-view render of the Nemo device. Layout follows the 3D-printed case
 * (object_finder_clip.scad): 52 x 80 mm body, teal lens ring at the top, one
 * small button in the middle, screen window below.
 *
 * TODO: this is a stand-in. Replace with the 3D model / real product image once
 * the team shares a photo of the finished device. Every product image on the
 * site goes through this one component, so swapping it here updates them all.
 */
export function ClipVisual({ className, idPrefix = "clip" }: { className?: string; idPrefix?: string }) {
  const id = (n: string) => `${idPrefix}-${n}`;
  return (
    <svg viewBox="0 0 260 392" className={className} role="img" aria-labelledby={id("t")} xmlns="http://www.w3.org/2000/svg">
      <title id={id("t")}>
        Nemo: a small rounded navy device about the size of a deck of cards, with a tiny camera lens near the top, one coral
        button in the middle and a small screen below it.
      </title>
      <defs>
        <linearGradient id={id("body")} x1="0.15" y1="0" x2="0.85" y2="1">
          <stop offset="0" stopColor="#2C5582" />
          <stop offset="0.45" stopColor={colors.navy} />
          <stop offset="1" stopColor="#132B44" />
        </linearGradient>
        <linearGradient id={id("edge")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.28" />
          <stop offset="0.35" stopColor="#fff" stopOpacity="0.04" />
          <stop offset="1" stopColor="#000" stopOpacity="0.25" />
        </linearGradient>
        <radialGradient id={id("glass")} cx="0.35" cy="0.3" r="0.8">
          <stop offset="0" stopColor="#4FB7BE" stopOpacity="0.9" />
          <stop offset="0.35" stopColor="#123049" />
          <stop offset="1" stopColor="#050D16" />
        </radialGradient>
        <radialGradient id={id("btn")} cx="0.42" cy="0.32" r="0.75">
          <stop offset="0" stopColor="#FF9C82" />
          <stop offset="0.7" stopColor={colors.coral} />
          <stop offset="1" stopColor="#E9694A" />
        </radialGradient>
        <radialGradient id={id("well")} cx="0.5" cy="0.6" r="0.6">
          <stop offset="0.75" stopColor="#0E2238" />
          <stop offset="1" stopColor="#1A3958" />
        </radialGradient>
        <filter id={id("soft")} x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="10" />
        </filter>
      </defs>

      {/* floor shadow */}
      <ellipse cx="130" cy="362" rx="92" ry="12" fill={colors.navy} opacity="0.22" filter={`url(#${id("soft")})`} />

      {/* metal clip peeking from behind */}
      <rect x="102" y="4" width="56" height="40" rx="10" fill="#A9B4BF" />
      <rect x="110" y="10" width="40" height="6" rx="3" fill="#fff" opacity="0.45" />

      {/* body */}
      <rect x="30" y="24" width="200" height="308" rx="50" fill={`url(#${id("body")})`} />
      <rect x="31" y="25" width="198" height="306" rx="49" fill="none" stroke={`url(#${id("edge")})`} strokeWidth="2" />

      {/* lens: teal ring, Ø20 mm, centre 23 mm above middle */}
      <circle cx="130" cy="90" r="38" fill="#0C1D30" />
      <circle cx="130" cy="90" r="34" fill="none" stroke={colors.aqua} strokeWidth="6" />
      <circle cx="130" cy="90" r="22" fill={`url(#${id("glass")})`} />
      <circle cx="130" cy="90" r="8" fill="#03080E" />
      <ellipse cx="122" cy="82" rx="6.5" ry="4" fill="#fff" opacity="0.7" transform="rotate(-35 122 82)" />

      {/* the one button: Ø9 mm cap, 6 mm above middle */}
      <circle cx="130" cy="155" r="22" fill={`url(#${id("well")})`} />
      <circle cx="130" cy="154" r="17" fill={`url(#${id("btn")})`} />
      <ellipse cx="130" cy="146" rx="9" ry="3.5" fill="#fff" opacity="0.28" />

      {/* screen window: 33 x 20 mm, 18 mm below middle, showing a snapshot */}
      <rect x="66" y="208" width="128" height="78" rx="8" fill="#050D16" />
      <rect x="66" y="208" width="128" height="78" rx="8" fill="none" stroke="#fff" strokeOpacity="0.1" strokeWidth="1.5" />
      <g transform="translate(78 220)">
        <rect width="104" height="40" rx="3" fill={colors.cream} opacity="0.14" />
        <path d="M0 30h104" stroke={colors.cream} strokeOpacity="0.35" strokeWidth="2" />
        <circle cx="40" cy="24" r="5" fill="none" stroke={colors.cream} strokeOpacity="0.85" strokeWidth="2" />
        <path d="M44 27l9 3" stroke={colors.cream} strokeOpacity="0.85" strokeWidth="2" strokeLinecap="round" />
        <circle cx="45" cy="25" r="14" fill="none" stroke={colors.coral} strokeWidth="2" strokeDasharray="3 3" />
        <rect y="47" width="62" height="5" rx="2.5" fill={colors.aqua} opacity="0.8" />
      </g>

      {/* edge vents (mic / speaker) */}
      <g stroke={colors.cream} strokeOpacity="0.28" strokeWidth="3.5" strokeLinecap="round">
        <path d="M108 310h44" />
      </g>
    </svg>
  );
}
