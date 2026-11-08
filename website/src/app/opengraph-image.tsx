import { ImageResponse } from "next/og";
import { colors } from "@/theme/tokens";
import { logoSvgString } from "@/components/Logo";
import { site } from "@/content/site";

// TODO: swap for a designed OG image with a real product photo once available.
export const alt = "Nemo: Nemo remembers, so you don't have to.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  const logo = `data:image/svg+xml;base64,${Buffer.from(logoSvgString("navy")).toString("base64")}`;
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          background: colors.cream,
          color: colors.navy,
        }}
      >
        <img src={logo} width={260} height={60} alt="" />
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ fontSize: 76, fontWeight: 700, lineHeight: 1.08, letterSpacing: "-0.02em", maxWidth: 900 }}>
            {site.tagline}
          </div>
          <div style={{ fontSize: 34, color: colors.charcoal, maxWidth: 900 }}>
            A small wearable that remembers where you put things.
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ display: "flex", background: colors.coral, color: colors.navy, fontSize: 30, fontWeight: 700, padding: "14px 32px", borderRadius: 999 }}>
            {site.ask}
          </div>
          <div style={{ fontSize: 26, color: colors.charcoal }}>Built at HackUTD 2026</div>
        </div>
      </div>
    ),
    size,
  );
}
