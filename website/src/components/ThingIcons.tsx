/** Simple line drawings of the everyday things Nemo finds. Decorative. */
const common = {
  width: 28,
  height: 28,
  viewBox: "0 0 32 32",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export const ThingIcon = {
  keys: () => (
    <svg {...common}>
      <circle cx="10" cy="11" r="5.5" />
      <path d="M14 15l11 11M21 22l3-3M18 19l2.5-2.5" />
    </svg>
  ),
  glasses: () => (
    <svg {...common}>
      <circle cx="9" cy="19" r="5" />
      <circle cx="23" cy="19" r="5" />
      <path d="M14 18.5c1.2-1 2.8-1 4 0M4 18l2-7M28 18l-2-7" />
    </svg>
  ),
  remote: () => (
    <svg {...common}>
      <rect x="11" y="3" width="10" height="26" rx="3.5" />
      <circle cx="16" cy="9" r="1.8" />
      <path d="M14 15h4M14 19h4M14 23h4" />
    </svg>
  ),
  pillbox: () => (
    <svg {...common}>
      <rect x="3" y="9" width="26" height="15" rx="3" />
      <path d="M3 14h26M9.5 9v15M16 9v15M22.5 9v15" />
    </svg>
  ),
};
