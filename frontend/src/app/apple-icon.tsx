import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "#0A0A0A",
          color: "#10B981",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "monospace",
          fontWeight: 700,
          letterSpacing: "-0.05em",
        }}
      >
        <div style={{ fontSize: 120, lineHeight: 1 }}>G</div>
        <div
          style={{
            fontSize: 14,
            marginTop: 8,
            color: "#737373",
            letterSpacing: "0.2em",
          }}
        >
          GONGSI
        </div>
      </div>
    ),
    { ...size },
  );
}
