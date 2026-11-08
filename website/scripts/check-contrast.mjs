// Checks WCAG 2.1 contrast for the brand colour pairs used on the site.
// Run: npm run check:contrast
const c = {
  navy: "#1B3A5B",
  coral: "#FF7A59",
  cream: "#F7F3EC",
  aqua: "#3B9FA6",
  charcoal: "#2B2B2B",
  white: "#FFFFFF",
};

const lum = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const f = (v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
};
const ratio = (a, b) => {
  const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
};

// [foreground, background, how it's used, required ratio]
const pairs = [
  ["navy", "cream", "headings & text on cream", 4.5],
  ["charcoal", "cream", "body text on cream", 4.5],
  ["charcoal", "white", "text in form fields", 4.5],
  ["cream", "navy", "text on navy sections", 4.5],
  ["navy", "coral", "primary button label", 4.5],
  ["coral", "navy", "coral accents on navy (graphics/large)", 3],
  ["white", "aqua", "icons on aqua tiles (graphics)", 3],
  ["aqua", "navy", "aqua accents on navy (graphics)", 3],
  ["coral", "cream", "NOT USED for text — fill/highlight only", 0],
  ["aqua", "cream", "NOT USED for text — decorative only", 0],
];

let failed = false;
for (const [fg, bg, use, need] of pairs) {
  const r = ratio(c[fg], c[bg]);
  const ok = need === 0 ? "—  " : r >= need ? "✅ " : "❌ ";
  if (need && r < need) failed = true;
  console.log(`${ok}${fg.padEnd(9)} on ${bg.padEnd(6)} ${r.toFixed(2).padStart(5)}:1  (${use}${need ? `, needs ${need}:1` : ""})`);
}
process.exit(failed ? 1 : 0);
