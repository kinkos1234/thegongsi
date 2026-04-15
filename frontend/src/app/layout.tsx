import type { Metadata } from "next";
import { NavBar } from "@/components/NavBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "comad-stock — DART-native AI 주식 리서치",
  description: "한국 주식을 위한 오픈소스 AI 리서치 터미널. DART 공시 + GraphRAG + DD 메모.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <NavBar />
        {children}
      </body>
    </html>
  );
}
