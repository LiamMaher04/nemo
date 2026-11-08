import { colors } from "@/theme/tokens";

/**
 * The Nemo wordmark: lowercase, rounded monoline letters with the "o" drawn as
 * a coral camera lens: a ring with a centre dot, like a gentle "found it" mark.
 * Drawn as paths (not text) so it renders identically everywhere.
 */
export const LOGO_PATHS = {
  letters: [
    "M5 16V50", // n stem
    "M5 30A14 14 0 0 1 33 30V50", // n arch
    "M49 33H83A17 17 0 1 0 78 45", // e
    "M98 16V50", // m stem
    "M98 28A12 12 0 0 1 122 28V50", // m first arch
    "M122 28A12 12 0 0 1 146 28V50", // m second arch
  ],
  lens: { cx: 178, cy: 33, r: 17, dot: 5.5 },
  viewBox: "0 10 200 46",
  stroke: 9,
};

type LogoProps = {
  className?: string;
  tone?: "navy" | "cream";
  /** Set when the logo sits inside a link that already has an accessible name. */
  decorative?: boolean;
};

export function Logo({ className, tone = "navy", decorative = false }: LogoProps) {
  const ink = tone === "navy" ? colors.navy : colors.cream;
  const { letters, lens, viewBox, stroke } = LOGO_PATHS;
  return (
    <svg
      viewBox={viewBox}
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      {...(decorative ? { "aria-hidden": true, focusable: false } : { role: "img", "aria-label": "Nemo" })}
    >
      <g fill="none" stroke={ink} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round">
        {letters.map((d) => (
          <path key={d} d={d} />
        ))}
      </g>
      <circle cx={lens.cx} cy={lens.cy} r={lens.r} fill="none" stroke={colors.coral} strokeWidth={stroke} />
      <circle cx={lens.cx} cy={lens.cy} r={lens.dot} fill={colors.coral} />
    </svg>
  );
}

/** Logo as a standalone SVG string (used for the OG image). */
export function logoSvgString(tone: "navy" | "cream" = "navy") {
  const ink = tone === "navy" ? colors.navy : colors.cream;
  const { letters, lens, viewBox, stroke } = LOGO_PATHS;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}"><g fill="none" stroke="${ink}" stroke-width="${stroke}" stroke-linecap="round" stroke-linejoin="round">${letters
    .map((d) => `<path d="${d}"/>`)
    .join("")}</g><circle cx="${lens.cx}" cy="${lens.cy}" r="${lens.r}" fill="none" stroke="${colors.coral}" stroke-width="${stroke}"/><circle cx="${lens.cx}" cy="${lens.cy}" r="${lens.dot}" fill="${colors.coral}"/></svg>`;
}
