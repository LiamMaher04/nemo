/**
 * Nemo design tokens: the single source of truth for colour and type.
 *
 * Tweak values here; Tailwind (tailwind.config.ts) and the CSS variables in
 * globals.css both read from this file's values, so changes flow everywhere.
 *
 * Contrast notes (WCAG 2.1, checked by `npm run check:contrast`):
 *  - navy on cream ............ 10.53:1  ✅ any text
 *  - charcoal on cream ........ 12.80:1  ✅ any text
 *  - navy on coral ............ 4.54:1  ✅ button labels (normal text AA)
 *  - coral on cream ........... 2.32:1  ❌ never use coral for text on cream -
 *                                         coral is a fill/highlight colour only
 *  - aqua on cream ............ 2.84:1  ❌ not for text; icons sit on aqua
 *                                         tiles in white instead (white on aqua 3.14:1, graphics AA)
 *  - cream on navy ............ 10.53:1  ✅ any text
 */

export const colors = {
  /** Primary: Deep sea navy: trust, depth, calm */
  navy: "#1B3A5B",
  /** Accent: Warm coral: the one thing to tap or notice. Use sparingly. */
  coral: "#FF7A59",
  /** Background: Soft cream: warm, not hospital white */
  cream: "#F7F3EC",
  /** Secondary: Fresh aqua: secondary icons and accents */
  aqua: "#3B9FA6",
  /** Text: Charcoal */
  charcoal: "#2B2B2B",
  /** Functional only: form-field fill. Not a brand colour. */
  white: "#FFFFFF",
} as const;

export const fonts = {
  /** Headlines: loaded with next/font in app/layout.tsx */
  heading: ["var(--font-poppins)", "ui-sans-serif", "system-ui", "sans-serif"],
  /** Body: loaded with next/font in app/layout.tsx */
  body: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
};

/**
 * Type scale. Body copy is 18px (1.125rem) minimum with generous line-height.
 * Format: [font-size, { lineHeight, letterSpacing? }]
 */
type FontSizeToken = [string, { lineHeight: string; letterSpacing?: string }];

export const fontSize: Record<string, FontSizeToken> = {
  sm: ["1rem", { lineHeight: "1.6" }], // 16px: short labels only, never body copy
  base: ["1.125rem", { lineHeight: "1.7" }], // 18px: body minimum
  lg: ["1.25rem", { lineHeight: "1.7" }], // 20px
  xl: ["1.5rem", { lineHeight: "1.5" }], // 24px
  "2xl": ["1.875rem", { lineHeight: "1.3" }], // 30px
  "3xl": ["2.25rem", { lineHeight: "1.2", letterSpacing: "-0.01em" }], // 36px
  "4xl": ["2.75rem", { lineHeight: "1.15", letterSpacing: "-0.015em" }], // 44px
  "5xl": ["3.5rem", { lineHeight: "1.08", letterSpacing: "-0.02em" }], // 56px
  "6xl": ["4.25rem", { lineHeight: "1.04", letterSpacing: "-0.03em" }], // 68px
  "7xl": ["5.5rem", { lineHeight: "1", letterSpacing: "-0.035em" }], // 88px: hero display
};

export const radius = {
  sm: "0.5rem",
  DEFAULT: "0.75rem",
  lg: "1rem",
  xl: "1.5rem",
  "2xl": "2rem",
  full: "9999px",
} as const;

export const shadow = {
  soft: "0 1px 2px rgba(27, 58, 91, 0.06), 0 8px 24px rgba(27, 58, 91, 0.08)",
  lift: "0 2px 4px rgba(27, 58, 91, 0.08), 0 16px 40px rgba(27, 58, 91, 0.14)",
} as const;

/** Hairlines do the work cards and shadows would otherwise do. */
export const hairline = {
  onCream: "rgba(27, 58, 91, 0.16)",
  onNavy: "rgba(247, 243, 236, 0.2)",
} as const;

export const layout = {
  /** Comfortable reading width for paragraphs */
  prose: "38rem",
  /** Max width of the page content */
  container: "76rem",
} as const;
