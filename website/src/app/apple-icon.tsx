import { ImageResponse } from "next/og";
import { colors } from "@/theme/tokens";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", background: colors.navy }}>
        <div style={{ width: 86, height: 86, borderRadius: 999, border: `20px solid ${colors.coral}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ width: 26, height: 26, borderRadius: 999, background: colors.coral }} />
        </div>
      </div>
    ),
    size,
  );
}
