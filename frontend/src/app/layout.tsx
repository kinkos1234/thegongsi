import type { Metadata } from "next";
import { NavBar } from "@/components/NavBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "The Gongsi · 더공시 — DART-native AI 주식 리서치",
  description: "Korean disclosures, deciphered. DART 공시 + GraphRAG + DD 메모. 오픈소스 AI 리서치 터미널.",
};

// FOUC/하이드레이션 방지 — HTML 파싱 직후 테마 즉시 적용
// 저장된 설정 없으면 prefers-color-scheme 존중
const THEME_INIT_SCRIPT = `
(function() {
  try {
    var saved = localStorage.getItem('comad_stock_theme');
    var prefersLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
    var theme = saved || (prefersLight ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <NavBar />
        {children}
      </body>
    </html>
  );
}
