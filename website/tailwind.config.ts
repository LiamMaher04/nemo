import type { Config } from "tailwindcss";
import { colors, fonts, fontSize, radius, shadow, layout } from "./src/theme/tokens";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    // Override (not extend) colours so only brand colours can be used.
    colors: {
      transparent: "transparent",
      current: "currentColor",
      ...colors,
    },
    fontSize,
    borderRadius: { none: "0", ...radius },
    extend: {
      fontFamily: {
        heading: fonts.heading,
        body: fonts.body,
      },
      boxShadow: shadow,
      maxWidth: {
        prose: layout.prose,
        container: layout.container,
      },
    },
  },
  plugins: [],
};

export default config;
