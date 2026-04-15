import type { Metadata } from "next";
import { NavBar } from "@/components/NavBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "The Gongsi · 더공시 — DART-native AI 주식 리서치",
  description: "Korean disclosures, deciphered. DART 공시 + GraphRAG + DD 메모. 오픈소스 AI 리서치 터미널.",
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
